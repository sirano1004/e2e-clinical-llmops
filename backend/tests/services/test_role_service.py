import asyncio
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

# --- Project Imports ---
# NOTE: The path might need adjustment based on the actual file structure.
from backend.schemas import DialogueTurn
from backend.services.role_service import role_service
# Example of alternative paths (commented out)
# from schemas import DialogueTurn
# from ...services.role_service import role_service

# ====================================================================
# LLM Execution Mocking (Fake Response Setup)
# ====================================================================

# Define the JSON string the LLM should return when a Role Tagging request is received.
# Assume index 0, 2 are Doctor, and 1, 3 are Patient.
MOCK_LLM_RESPONSE = json.dumps({
    "0": "Doctor",
    "1": "Patient",
    "2": "Doctor",
    "3": "Patient"
})

# Define the Mock asynchronous function that mimics llm_service._execute_prompt.
async def mock_execute_prompt(*args, **kwargs):
    """
    Simulates the LLM call without actually running vLLM.
    """
    print("MOCK: Returning predefined JSON response instead of LLM inference...")
    # Returns the JSON string as if it were a real response.
    return MOCK_LLM_RESPONSE

# ====================================================================
# Test Function
# ====================================================================

async def test_assign_roles_scenario():
    """
    Tests the functionality of RoleService.assign_roles.
    """
    print("--- Role Assignment Test Start ---")

    # 1. Create sample input data (Roles set to 'TBD' as if from the Transcriber)
    input_conversation = [
        DialogueTurn(role="TBD", content="Hello, how can I help you today?", chunk_index=0),
        DialogueTurn(role="TBD", content="Hi Doctor, I have a persistent cough and fever.", chunk_index=0),
        DialogueTurn(role="TBD", content="I see. How long have you had these symptoms?", chunk_index=0),
        DialogueTurn(role="TBD", content="About three days now.", chunk_index=0),
    ]

    # 2. Replace the LLM Handler's _execute_prompt function with the Mock.
    # Use @patch to substitute the actual function with our fake function.
    # NOTE: llm_service is a singleton instance.
    with patch('backend.services.llm_handler.llm_service._execute_prompt', new=mock_execute_prompt):
        
        # 3. Call assign_roles
        # Inside this function, the Mock function executes, and updates roles with the result.
        updated_turns = await role_service.assign_roles(input_conversation)
    
    # 4. Validate and Print Results
    print("\n--- Test Result ---")
    print(f"Total Turns Processed: {len(updated_turns)}")
    
    # Verify against expected results
    expected_roles = ["Doctor", "Patient", "Doctor", "Patient"]
    
    for i, turn in enumerate(updated_turns):
        print(f"[{i}] Role: {turn.role} (Expected: {expected_roles[i]}) | Content: {turn.content[:40]}...")
        assert turn.role == expected_roles[i], f"Assertion Failed: Turn {i} role is {turn.role}, expected {expected_roles[i]}"
        
    print("\n✅ All role assignments passed successfully!")

# ====================================================================
# Main Execution
# ====================================================================

if __name__ == "__main__":
    # Use asyncio.run() to execute the asynchronous function
    try:
        asyncio.run(test_assign_roles_scenario())
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("This might be a path issue. Please adjust the paths for 'backend.schemas' and 'backend.services.role_service' relative to your current execution location.")