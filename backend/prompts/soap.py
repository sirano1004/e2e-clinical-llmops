def get_suffix(task_type: str, context: str) -> str:
    """
    Returns the instruction suffix for SOAP tasks.
    Enforces JSON output with Lists of Strings.
    
    Update: Now includes COMPLETE examples to ensure the LLM 
    uses the correct keys (subjective, objective, assessment, plan).
    """
    
    # [Incremental Update Mode]
    # We show a multi-key example to prove it can update any section,
    # but still emphasize "Partial JSON" to save tokens.
    return (
        f"--- CURRENT NOTES ---\n"
        f"{context}\n\n"
        f"--- INSTRUCTION ---\n"
        f"The dialogue above has continued.\n"
        f"TASK: Create an INCREMENTAL UPDATE of the SOAP note. Identify and output ONLY the NEW CLINICAL information or CORRECTIONS.\n" # Explicit job assignment
        f"1. **IGNORE ALL** non-clinical discussion (greetings, MRN checks, PII confirmation, scheduling, non-symptom related chatter).\n"
        f"2. Compare new dialogue with 'Current Notes'.\n"
        f"3. If new clinical info (symptoms, history, findings, plan) is found, append it to the relevant list.\n"
        f"4. \n"
        f"   - **Use (Updated) ONLY IF** the new dialogue explicitly corrects a fact found in 'Current Notes'.\n"
        f"   - **DO NOT** use (Updated) for purely new information.\n"
        f"5. Output a PARTIAL JSON containing ONLY the new/updated items as LISTS.\n"
        f"   (Valid keys: subjective, objective, assessment, plan)\n\n"
        f"Example Output:\n"
        f"{{\n"
        f"  \"subjective\": [\"Right leg pain (Updated)\"],\n"
        f"  \"plan\": [\"Scheduled X-ray for tomorrow\"]\n"
        f"}}"
    )