def get_suffix(task_type: str, context: str) -> str:
    """
    Returns the instruction suffix for SOAP tasks.
    Enforces JSON output with Lists of Strings.
    
    Update: Now includes COMPLETE examples to ensure the LLM 
    uses the correct keys (subjective, objective, assessment, plan).
    """
    
    if task_type == "soap_final":
        # [Finalize Mode]
        # We provide a FULL JSON example to force the LLM to fill all sections.
        return (
            f"--- END OF SESSION ---\n"
            f"Draft Notes: {context}\n\n"
            f"TASK: Finalize the SOAP Note based on the FULL history above.\n"
            f"1. Resolve contradictions and merge duplicates.\n"
            f"2. Output strictly as a JSON object where values are LISTS of strings.\n"
            f"3. Ensure ALL 4 keys (subjective, objective, assessment, plan) are present.\n\n"
            f"Example Output:\n"
            f"{{\n"
            f"  \"subjective\": [\"Patient reports severe headache since morning.\", \"Nausea.\"],\n"
            f"  \"objective\": [\"BP 130/85.\", \"No neurological deficits.\"],\n"
            f"  \"assessment\": [\"Migraine.\", \"Dehydration.\"],\n"
            f"  \"plan\": [\"Prescribed Sumatriptan.\", \"Advised rest.\"]\n"
            f"}}"
        )
    
    else:
        # [Incremental Update Mode]
        # We show a multi-key example to prove it can update any section,
        # but still emphasize "Partial JSON" to save tokens.
        return (
            f"--- CURRENT NOTES ---\n"
            f"{context}\n\n"
            f"--- INSTRUCTION ---\n"
            f"The dialogue above has continued.\n"
            f"TASK: Extract NEW information to update the notes.\n"
            f"1. Compare new dialogue with 'Current Notes'.\n"
            f"2. If new info is found, append it to the list.\n"
            f"3. If previous info is corrected by the patient, append the new fact with '(Updated)'.\n"
            f"4. Output a PARTIAL JSON containing ONLY the new/updated items as LISTS.\n"
            f"   (Valid keys: subjective, objective, assessment, plan)\n\n"
            f"Example Output:\n"
            f"{{\n"
            f"  \"subjective\": [\"Right leg pain (Updated)\"],\n"
            f"  \"plan\": [\"Scheduled X-ray for tomorrow\"]\n"
            f"}}"
        )