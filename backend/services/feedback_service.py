import Levenshtein
from typing import Dict, Any, Optional
from datetime import datetime

# --- Project Imports ---
from ..core.local_storage import local_storage
from ..core.config import settings
from ..core.logger import logger
from ..prompts import get_system_prompt, get_suffix_prompt # 💡 Reconstruct Prompt
# Repositories
from ..repositories.conversation import conversation_service
from ..repositories.documents import document_service
from ..repositories.metrics import metrics_service

class FeedbackService:
    """
    Manages collection of Human Feedback with Accept/Reject/Edit workflows.
    Includes explicit stat updates for every action type.
    """

    async def save_feedback(
        self, 
        session_id: str, 
        task_type: str, 
        original_output: str, 
        edited_output: Optional[str], 
        action: str 
    ) -> Dict[str, Any]:
        """
        Processes feedback based on Doctor's Action:
        - Accept: Trust the AI output (SFT), but do NOT treat as 100% similarity (lazy accept).
        - Reject: Discard bad generation (No training data, but update stats).
        - Edit:  Analyze changes for SFT or DPO routing.
        """

        # 1. Define 'Chosen' and Calculate Metrics
        # If Accept, chosen is original. If Edit, chosen is edited.
        final_output = original_output if action == "accept" else (edited_output or original_output)
        
        # Calculate similarity ONLY for 'edit'.
        # For 'accept' (lazy user) and 'reject' (bad output), we set metrics to None.
        if action == "edit":
            metrics = self._calculate_edit_metrics(original_output, final_output)
            similarity = metrics["similarity"]
            distance = metrics["distance"]
        else:
            # Both 'accept' and 'reject' have no metric calculation
            similarity = None
            distance = None
            metrics = {"similarity": None, "distance": None}

        # 2. ⚡️ Update Session Stats in Redis (CRITICAL)
        # We MUST update stats even for 'reject' to track the Failure Rate.
        # similarity/distance are passed as None for 'accept'/'reject' based on discussion.
        await metrics_service.update_feedback_stats(
            session_id=session_id,
            similarity=similarity,
            distance=distance,
            action=action
        )

        # 3. Handle 'Reject' Early
        # If rejected, we logged the failure in Redis above, but we do NOT save it to SFT/DPO.
        if action == "reject":
            logger.warning(f"🗑️ Feedback Rejected: Stats updated, but data discarded.")
            return metrics

        # 4. Prepare Context for Training Data (Input)
        # Fetch what the AI saw to generate this output
        history = await conversation_service.get_dialogue_history(session_id)
        prev_note = await document_service.get_soap_note(session_id)
        
        history_text = "\n".join([f"{t.role}: {t.content}" for t in history])
        prev_note_str = prev_note.model_dump_json(indent=2) if prev_note and task_type != 'soap' else "None"
        
        sys_prompt = get_system_prompt(task_type)
        suffix_prompt = get_suffix_prompt(task_type, "[NOTE_CONTEXT]")

        # 5. Construct Training Record
        record = {
            "session_id": session_id,
            "model_id": settings.target_model,
            "task_type": task_type,
            "timestamp": datetime.now().isoformat(),
            "action": action, 
            "input_context": {
                "system_prompt": sys_prompt,
                "history": history_text,
                "previous_note": prev_note_str,
                "suffix_prompt": suffix_prompt 
            },
            "metrics": metrics,
            "chosen": final_output,     # Ground Truth
            "rejected": original_output # AI output (if edited)
        }

        # 6. Routing Logic (SFT vs DPO)
        
        # CASE A: Accept (Direct SFT)
        if action == "accept":
            logger.info(f"💾 [SFT] Saved (Accepted). Metrics: None")
            await local_storage.append_record(settings.sft_file, record)
            return metrics

        # CASE B: Edit (Correction)
        # Strategy:
        # - High Sim (>=0.9): Minor typo fixes -> SFT 
        # - Low Sim (<0.7): Complete rewrite -> SFT 
        # - Mid Sim (0.7~0.9): Preference Zone -> DPO 
        
        # We know similarity is NOT None here because action is 'edit'
        if similarity >= 0.9 or similarity < 0.7:
            logger.info(f"💾 [SFT] Saved (Edit - Correction). Sim: {similarity:.2f}")
            await local_storage.append_record(settings.sft_file, record)
        else:
            logger.info(f"💾 [DPO] Saved (Edit - Preference). Sim: {similarity:.2f}")
            await local_storage.append_record(settings.dpo_file, record)

        return metrics

    async def save_session_metrics(self, session_id: str):
        """
        Flushes the aggregated metrics (Guardrail + Active Feedback) to storage.
        """
        # 1. Retrieve all metrics from Redis
        # Now includes both NER counts and Feedback sums
        metrics = await metrics_service.get_metrics(session_id)
        
        if not metrics:
            return 
            
        # --- A. Guardrail Metrics (Automated) ---
        transcript_count = int(metrics.get("transcript_count") or 0)
        summary_count = int(metrics.get("summary_count") or 0)
        matched_count = int(metrics.get("matched_count") or 0)
        edit_count = int(metrics.get("edit_count") or 0)
        
        recall = matched_count / transcript_count if transcript_count > 0 else 0.0
        precision = matched_count / summary_count if summary_count > 0 else 0.0
        
        # --- B. Active Feedback Metrics (Human) ---
        feedback_indc = metrics.get("feedback_indc", 0)
        
        feedback_stats = None # Default to None if no feedback
        
        if feedback_indc > 0:
            total_sim = float(metrics.get("total_similarity") or 0.0)
            total_dist = int(metrics.get("total_edit_distance") or 0)
            accept_count = int(metrics.get("accept_count") or 0)
            reject_count = int(metrics.get("reject_count") or 0)
            edit_count = int(metrics.get("edit_count") or 0)

            feedback_stats = {
                "similarity": total_sim if edit_count > 0 else None,
                "edit_distance": total_dist if edit_count > 0 else None,
                "accept_count":accept_count,
                "reject_count": reject_count,
                "edit_count": edit_count
            }

        # --- C. Latency Metrics ---
        total_chunks = await conversation_service.get_next_chunk_index(session_id) - 1
        if total_chunks > 0:
            avg_chunk_latency = float(metrics.get("total_latency_ms") or 0.0) / total_chunks
            final_latency = float(metrics.get("final_e2e_latency_ms") or 0.0)
        else:
            avg_chunk_latency = None
            final_latency = None

        # 3. Create Log Record
        log_record = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "model_id": settings.target_model,
            "type": "session_summary", 
            "stats": {
                # Guardrail (Safety)
                "recall": round(recall, 4),
                "precision": round(precision, 4),
                "hallucination_rate": round(1.0 - precision, 4),
                # Human Feedback (Quality)
                "human_feedback": feedback_stats, # None or Dict
                # Latency Metrics (System Quality)
                "avg_chunk_latency": avg_chunk_latency,
                "final_latency": final_latency
            }
        }
        
        # 4. Save to System Log
        await local_storage.append_record(settings.metrics_file, log_record)
        
        logger.info(f"📊 Session Metrics Saved. Recall: {recall:.2%}")

    def _calculate_edit_metrics(self, original: str, edited: str) -> Dict[str, Any]:
        """
        Calculates Levenshtein distance and normalized similarity.
        """
        if not original or not edited:
            return {"distance": 0, "similarity": 0.0}

        dist = Levenshtein.distance(original, edited)
        max_len = max(len(original), len(edited))
        
        if max_len == 0:
            similarity = 1.0
        else:
            similarity = 1 - (dist / max_len)

        return {
            "distance": dist,
            "similarity": round(similarity, 4)
        }

# Singleton Instance
feedback_service = FeedbackService()