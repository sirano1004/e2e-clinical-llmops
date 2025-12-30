import json
import os
import glob
from typing import Any, Dict, List

from backend.services.guardrail_service import GuardrailService
from backend.schemas import SOAPNote
from data_pipeline.dedup.path import DedupPaths
from data_pipeline.config import settings


def run_guardrail(
    svc: GuardrailService,
    transcript: List[Dict[str, Any]],
    summary: Dict[str, Any],
    chunk_index: int
) -> List[str]:
    """
    Executes the backend Guardrail logic (NER + NLI) on a specific chunk.
    
    Args:
        svc: Initialized GuardrailService instance.
        transcript: List of dialogue turns (dicts).
        summary: The generated SOAP note (dict or text).
        chunk_index: The specific chunk ID to filter the transcript by.
        
    Returns:
        List of warning strings (e.g., "Unverified entity: 'diabetes'"). 
        Returns empty list if passed.
    """
    
    # Filter transcript turns belonging to the current chunk_index
    # User Note: "chunk_index" exists inside each item of the 'history' list.
    target_turns = [
        t['content'] 
        for t in transcript 
        if t.get('chunk_index') == chunk_index
    ]
    
    # If no turns matched the chunk_index, fallback to using all content 
    # (Safety net to prevent empty input to NER)
    if not target_turns:
        transcript_text = "\n".join([t.get('content', '') for t in transcript])
    else:
        transcript_text = "\n".join(target_turns)

    # 1. Clean Summary (Remove '(Updated)' tags, flatten JSON to string)
    summary_text = svc._clean_summary(summary)
    
    # 2. Run Analysis (NER + NLI)
    # Using the sync method directly to avoid async overhead in this script
    result = svc._run_analysis_sync(transcript_text, summary_text)

    return result.get("warnings", [])


def process_file(input_path: str, quality_path: str, quarantine_path: str, svc: GuardrailService) -> None:
    """
    Reads a JSONL file, validates each record, and splits them into 
    'quality' (passed) or 'quarantine' (failed) files.
    """
    total = 0
    passed = 0
    failed = 0

    print(f"   ➡️ Processing: {os.path.basename(input_path)}...")

    with open(input_path, "r", encoding="utf-8") as fin, \
         open(quality_path, "w", encoding="utf-8") as fout, \
         open(quarantine_path, "w", encoding="utf-8") as qout:
        
        for line in fin:
            line = line.strip()
            if not line:
                continue

            total += 1
            try:
                rec = json.loads(line)

                # Extract Key Data
                history = rec.get("history", [])
                chunk_index = rec.get("chunk_index", 0)
                
                # Extract Completion (Fall back to empty structure if missing)
                summary = rec.get("completion") or SOAPNote().model_dump(mode="json")

                # --- RUN QA CHECK ---
                warnings = run_guardrail(svc, history, summary, chunk_index)

                # Tagging the record
                rec["qa_warnings"] = warnings
                rec["qa_pass"] = (len(warnings) == 0)

                # Routing (Filter Logic)
                if rec["qa_pass"]:
                    passed += 1
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                else:
                    failed += 1
                    # We save the reason for failure in the quarantine file
                    qout.write(json.dumps(rec, ensure_ascii=False) + "\n")                

            except Exception as e:
                # Error handling: Save broken records to quarantine with error msg
                failed += 1
                bad_record = {"_qa_error": str(e), "_raw_line": line}
                qout.write(json.dumps(bad_record, ensure_ascii=False) + "\n")
                continue

    print(f"   ✅ Done: Total={total}, Passed={passed}, Failed={failed}")


def process_target(target: str, input_dir: str, quality_dir: str, quarantine_dir: str, svc: GuardrailService):
    """
    Finds all files matching the target pattern (e.g., sft_*.jsonl) and processes them.
    """
    # Pattern: input_dir/sft_*.jsonl
    pattern = os.path.join(input_dir, f"{target}*.jsonl")
    files = sorted(glob.glob(pattern))    
    
    if not files:
        print(f"⚠️ No files found for target '{target}' in {input_dir}")
        return  
    
    print(f"🔍 Found {len(files)} files for target '{target}'")

    for input_path in files:
        fname = os.path.basename(input_path)
        
        # Define output paths
        quality_path = os.path.join(quality_dir, fname)
        quarantine_path = os.path.join(quarantine_dir, fname)

        process_file(input_path, quality_path, quarantine_path, svc)


def main():
    # 1. Initialize Backend Guardrail Service (Loads BERT/DeBERTa models)
    # This might take a few seconds/minutes depending on GPU/CPU
    print("🚀 Initializing Guardrail Service (Loading Models)...")
    svc = GuardrailService(redis_client=None)  # No Redis needed for offline processing

    # 2. Setup Paths
    # We use empty strings for unused dirs in DedupPaths to retrieve the final_output path
    dedup_paths = DedupPaths("", "", os.path.join(settings.data_dir, settings.dedup_data_dir, settings.soft_dedup_dir), "")
    
    input_dir = dedup_paths.final_output() # Source: dedup/soft/outputs
    quality_dir = os.path.join(settings.data_dir, settings.qa_dir, settings.quality_data_dir)
    quarantine_dir = os.path.join(settings.data_dir, settings.qa_dir, settings.quarantine_data_dir)

    # Create directories
    os.makedirs(quality_dir, exist_ok=True)
    os.makedirs(quarantine_dir, exist_ok=True)

    print(f"📂 Input Directory: {input_dir}")
    print(f"📂 Quality Output: {quality_dir}")
    print(f"📂 Quarantine Output: {quarantine_dir}")

    # 3. Run for targets
    targets = ['sft', 'dpo']
    for target in targets:
        process_target(target, input_dir, quality_dir, quarantine_dir, svc)

    print("\n🎉 QA Pipeline Completed Successfully!")


if __name__ == "__main__":
    main()