import json
import re
from typing import List, Dict, Tuple

# --- Project Imports ---
from ..services.llm_handler import llm_service
from ..schemas import DialogueTurn

class RoleService:
    """
    Service dedicated to inferring speaker roles (Doctor vs Patient) 
    from raw transcripts using semantic context.
    """
    
    async def assign_roles(self, conversation: List[DialogueTurn]) -> Tuple[List[DialogueTurn], Dict[str, str]]:
        """
        Main entry point.
        1. Generates a snippet from the conversation.
        2. Queries the LLM to identify roles.
        3. Updates the DialogueTurn objects with new roles.
        
        Returns:
            - Updated list of DialogueTurns
            - The role mapping dict (e.g., {'SPEAKER_01': 'Doctor'}) 
              (Useful if app.py needs to update other data structures like raw_segments)
        """
        # 1. Create a text snippet (First 15 turns are usually enough to identify context)
        # Sending the whole transcript is unnecessary and wastes tokens.
        snippet_parts = []
        for turn in conversation[:15]:
            snippet_parts.append(f"{turn.role}: {turn.content}")
        snippet = "\n".join(snippet_parts)

        # 2. Ask LLM to infer roles
        print("🕵️ Inferring speaker roles from context...")
        role_map = await self._infer_roles_from_llm(snippet)
        
        if not role_map:
            print("⚠️ Role inference failed or returned empty. Keeping original labels.")
            return conversation, {}

        # 3. Apply the role mapping to the full conversation
        print(f"✅ Applying Role Map: {role_map}")
        updated_conversation = []
        
        for turn in conversation:
            # Check if the current role (e.g., SPEAKER_01) exists in our map
            # If yes, replace it (e.g., 'Doctor'). If no, keep original.
            new_role = role_map.get(turn.role, turn.role)
            
            # Create a copy of the Pydantic model with the updated role
            # (Pydantic models are immutable by default in some configs, this is safer)
            updated_turn = turn.model_copy(update={"role": new_role})
            updated_conversation.append(updated_turn)
            
        return updated_conversation, role_map

    async def _infer_roles_from_llm(self, snippet: str) -> Dict[str, str]:
        """
        Sends the snippet to the LLM and parses the JSON response.
        """
        # System prompt designed to force strict JSON output for mapping
        system_prompt = (
            "Analyze the provided medical consultation snippet. "
            "Identify which Speaker ID corresponds to the 'Doctor' and which to the 'Patient'.\n"
            " - Doctors typically ask questions about symptoms, history, or medications.\n"
            " - Patients typically describe pain, answer questions, or express concerns.\n\n"
            "Output ONLY a valid JSON object mapping the ID to the Role.\n"
            "Example format: {\"SPEAKER_01\": \"Doctor\", \"SPEAKER_00\": \"Patient\"}\n"
            "Do not include markdown code blocks or explanation."
        )
        
        try:
            # Reuse the low-level execution function from llm_service
            # We use temperature=0.0 for deterministic logical reasoning
            response_text = await llm_service._execute_prompt(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": snippet}
                ],
                temperature=0.0
            )
            
            # Parsing Logic
            text = response_text.strip()
            
            # Remove potential Markdown code blocks (e.g., ```json ... ```)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "{" in text:
                # Fallback: extract the first JSON-like object found
                text = text[text.find("{"):text.rfind("}")+1]
                
            return json.loads(text)

        except Exception as e:
            print(f"❌ Role Inference Error: {e}")
            return {}

# Singleton Instance
role_service = RoleService()