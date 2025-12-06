# backend/prompts/referral.py

def get_suffix(task_type: str, context: str) -> str:
    """
    Returns instructions for generating a Referral Letter.
    Enforces Plain Text output (No JSON).
    """
    return (
        f"--- REFERENCE: FINAL SOAP NOTE ---\n"
        f"{context}\n\n"
        f"TASK: Write a formal Referral Letter based on the dialogue and SOAP note above.\n"
        f"Output Format: PLAIN TEXT ONLY.\n"
        f"Constraints:\n"
        f"1. Do NOT use JSON.\n"
        f"2. Do NOT include conversational fillers like 'Here is the letter'.\n"
        f"3. Start directly with 'Date:' or 'To Dr. [Name]'.\n"
        f"4. Include patient demographics if available, otherwise use placeholders."
    )