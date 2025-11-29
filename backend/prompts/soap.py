# 1. The Core Instruction
SYSTEM_INSTRUCTION = (
    "You are an expert medical scribe. "
    "Your output must be a strict JSON object containing the keys: "
    "subjective, objective, assessment, plan."
)

# 2. Few-Shot Examples (Crucial for accuracy)
# Adding examples here makes the model much smarter.
FEW_SHOT_EXAMPLES = """
Example Input:
Patient: My head hurts and I feel dizzy.
Doctor: How long?
Patient: Since yesterday.

Example Output:
{
  "subjective": "Patient reports headache and dizziness starting yesterday.",
  "objective": "None reported.",
  "assessment": "Potential tension headache or migraine.",
  "plan": "Monitor symptoms."
}
"""

def get_prompt():
    return f"{SYSTEM_INSTRUCTION}\n\n{FEW_SHOT_EXAMPLES}"