import Levenshtein
from typing import Dict, Any, Optional
from datetime import datetime

# --- Project Imports ---
from ..core.local_storage import local_storage
from ..core.config import settings
from ..core.logger import logger
from ..services.session_service import session_service # 💡 Fetch Context
from ..prompts import get_system_prompt, get_suffix_prompt # 💡 Reconstruct Prompt

class FeedbackService:
    """
    Manages collection of Human Feedback with Advanced Routing.
    Handling 'No Edit' scenarios specifically to prevent bad data ingestion.
    """

    async def save_feedback(
        self, 
        session_id: str, 
        task_type: str, 
        original_output: str, 
        edited_output: str, 
        rating: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes feedback.
        - No Edit + Thumbs Up: SFT (Good)
        - No Edit + Thumbs Down: Discard (Cannot learn)
        - Edited: Follows Beta-DPO routing logic.
        """

        # 1. Fetch Context from Redis (The "Input" part)
        # We need to know WHAT the AI was looking at when it generated the output.
        history = await session_service.get_dialogue_history(session_id)
        prev_note = await session_service.get_soap_note(session_id)
        
        # Serialize for storage
        history_text = "\n".join([f"{t.role}: {t.content}" for t in history])
        
        prev_note_str = prev_note.model_dump_json(indent=2) if prev_note and task_type != 'soap' else "None"
        
        # 2. Reconstruct the Full Prompt (For reproduction/training)
        # LLM Input = System + History + Suffix(Instruction + PrevNote)
        sys_prompt = get_system_prompt(task_type)
        suffix_prompt = get_suffix_prompt(task_type, "[NOTE_CONTEXT]")
        
        # 3. Metrics Calculation
        metrics = self._calculate_edit_metrics(original_output, edited_output)
        similarity = metrics["similarity"]
        distance = metrics["distance"]

        # 4. Record Construction
        record = {
            "session_id": session_id,
            "model_id": settings.target_model,
            "task_type": task_type,
            "timestamp": datetime.utcnow().isoformat(),
            "input_context": {
                "system_prompt": sys_prompt,
                "history": history_text,
                "previous_note": prev_note_str,
                "suffix_prompt": suffix_prompt 
            },
            "metrics": {
                "similarity_score": similarity,
                "edit_distance": distance,
                "user_rating": rating
            },
            "chosen": edited_output,    # Ground Truth
            "rejected": original_output # AI output
        }

        # 3. Routing Logic (The Brain)
        
        # Case A: No Edit (Perfect Match)
        if original_output == edited_output:
            if rating == "thumbs_down":
                # User hated it but didn't fix it. 
                # We have no positive signal to train on.
                logger.warning(f"⚠️ Feedback Ignored: Thumbs down with no edit. (Sim: 1.0)")
                return metrics
            else:
                # Thumbs up OR Implicit acceptance.
                # Reinforce this behavior.
                logger.info(f"💾 [SFT] Saved (Perfect Match). Sim: 1.0")
                await local_storage.append_record(settings.sft_file, record)
                return metrics

        # Case B: Edited (Correction)
        # User's Rule: SFT if (Easy OR Hard OR Explicit Dislike)
        is_sft = False
        if similarity >= 0.9 or similarity < 0.7 or rating == "thumbs_down":
            is_sft = True
        
        if is_sft:
            logger.info(f"💾 [SFT] Saved (Correction). Sim: {similarity:.2f}")
            await local_storage.append_record(settings.sft_file, record)
        else:
            # The "Goldilocks Zone" for DPO (0.7 <= Sim < 0.9)
            logger.info(f"💾 [DPO] Saved (Hard Negative). Sim: {similarity:.2f}")
            await local_storage.append_record(settings.dpo_file, record)

        return metrics

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