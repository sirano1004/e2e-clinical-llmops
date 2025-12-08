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
        "You are an expert medical scribe. "
        "Your specific role is to create a structured clinical SOAP note from the dialogue. "
        "Your output must be a strict JSON object containing the keys: "
        "subjective, objective, assessment, plan."
        f"The dialogue above has continued. Your job is to capture NEW clinical facts.\n"
        f"1. **IGNORE** greetings, small talk, and PII verification (Name/MRN checks).\n"
        f"2. **COMPARE** the dialogue with 'Current Notes'.\n"
        f"3. **EXTRACT** only new or corrected clinical info (Symptoms, Vitals, Plan).\n"
        f"4. **CRITICAL**: If the dialogue contains NO new clinical info, return empty lists. **DO NOT MAKE UP INFORMATION.**\n"
        f"5. **DO NOT COPY** the examples provided below. They are for format reference only.\n\n"
        f"--- FORMAT EXAMPLE (STRICTLY REFERENCE ONLY) ---\n"
        f"Input: 'I also have a sore throat since morning.'\n"
        f"Output:\n"
        f"{{\n"
        f"  \"subjective\": [\"Sore throat since morning\"],\n"
        f"  \"objective\": [],\n"
        f"  \"assessment\": [],\n"
        f"  \"plan\": []\n"
        f"}}\n"
        f"------------------------------------------------\n"
        f"Now, generate the JSON for the *actual dialogue* above."
    )