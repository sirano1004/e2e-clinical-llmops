# backend/prompts/certificate.py

def get_suffix(task_type: str, context: str) -> str:
    """
    Returns instructions for generating a Medical Certificate.
    Enforces Plain Text output (No JSON) and formal legal tone.
    """
    return (
        f"--- REFERENCE: FINAL SOAP NOTE ---\n"
        f"{context}\n\n"
        f"TASK: Write a formal Medical Certificate based on the SOAP note above.\n"
        f"Output Format: PLAIN TEXT ONLY.\n"
        f"Constraints:\n"
        f"1. Do NOT use JSON.\n"
        f"2. Do NOT include conversational fillers like 'Here is the certificate'.\n"
        f"3. Start directly with the title 'MEDICAL CERTIFICATE'.\n"
        f"4. Structure must include:\n"
        f"   - Patient Name & Demographics (use placeholders if missing)\n"
        f"   - Date of Exam\n"
        f"   - Diagnosis (Assessment)\n"
        f"   - Unfitness for work/school (Duration)\n"
        f"   - Doctor's Name/Signature placeholder\n"
        f"5. Keep the tone strictly formal and medico-legal."
    )