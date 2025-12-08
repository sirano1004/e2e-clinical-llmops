import json
import re
from typing import List, Dict, Tuple

# --- Project Imports ---
from ..services.llm_handler import llm_service
from ..schemas import DialogueTurn

# Import prompt
from ..prompts import get_system_prompt
from ..core.logger import logger

class RoleService:
    """
    Service dedicated to inferring speaker roles (Doctor vs Patient) 
    from raw transcripts using semantic context.
    """
    
    async def assign_roles(self, conversation: List[DialogueTurn]) -> Tuple[List[DialogueTurn], Dict[str, str]]:
        """
        Main entry point.
        1. Accepts the list of DialogueTurns (with 'TBD' roles) from Transcriber.
        2. Assigns roles using LLM tagging.
        3. Returns the updated list.
        """
        if not conversation:
            return []

        # 1. Prepare Input for LLM
        # We use 'index' as the ID because 'turn.role' is currently 'TBD'.
        tagged_input = []
        for i, turn in enumerate(conversation):
            tagged_input.append({
                "id": i, 
                "text": turn.content
            })
            logger.info(f"🏷️ Tagging Roles for {len(conversation)} turns...")

        # 2. Call LLM to get the ID -> Role mapping
        role_map = await self._get_roles_from_llm(tagged_input)
        
        # 3. Apply roles back to the DialogueTurns
        updated_conversation = []
        for i, turn in enumerate(conversation):
            # Default to "Unknown" if LLM missed the ID
            new_role = role_map.get(i, "Unknown")
            
            # Create a copy with the new role
            updated_turn = turn.model_copy(update={"role": new_role})
            updated_conversation.append(updated_turn)
            
        return updated_conversation

    async def _get_roles_from_llm(self, inputs: List[Dict]) -> Dict[int, str]:
        """
        Returns a map: {index: "Doctor" or "Patient"}
        """
        # Convert input list to JSON string for the prompt
        input_json = json.dumps(inputs, ensure_ascii=False)

        system_prompt = get_system_prompt("role_service")

        try:
            # Temperature 0.0 is best for classification tasks
            response_text = await llm_service._execute_prompt(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": input_json}
                ],
                temperature=0.0
            )
            
            # Parsing Logic
            text = response_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].strip()
            
            # Parse Map and convert keys to integers
            raw_map = json.loads(text)
            return {int(k): v for k, v in raw_map.items()}

        except Exception as e:
            logger.exception(f"❌ Role Tagging Failed: {e}")
            return {}

# Singleton Instance
role_service = RoleService()