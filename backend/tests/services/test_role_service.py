import asyncio
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

# --- Project Imports ---
# NOTE: 실제 파일 구조에 맞게 경로를 수정해야 할 수 있습니다.
from backend.schemas import DialogueTurn
from backend.services.role_service import role_service
# from schemas import DialogueTurn
# from ...services.role_service import role_service

# ====================================================================
# LLM 실행 Mocking (가짜 응답 설정)
# ====================================================================

# LLM이 Role Tagging 요청을 받았을 때 반환할 JSON 문자열을 정의합니다.
# DialogueTurn의 index 0, 2는 Doctor, 1, 3은 Patient로 가정합니다.
MOCK_LLM_RESPONSE = json.dumps({
    "0": "Doctor",
    "1": "Patient",
    "2": "Doctor",
    "3": "Patient"
})

# llm_service._execute_prompt 함수를 흉내내는 Mock 비동기 함수를 정의합니다.
async def mock_execute_prompt(*args, **kwargs):
    """
    Simulates the LLM call without actually running vLLM.
    """
    print("MOCK: LLM 추론 대신 미리 정해진 JSON 응답 반환...")
    # 실제 응답처럼 JSON 문자열을 리턴합니다.
    return MOCK_LLM_RESPONSE

# ====================================================================
# 테스트 함수
# ====================================================================

async def test_assign_roles_scenario():
    """
    RoleService.assign_roles 기능을 테스트합니다.
    """
    print("--- Role Assignment Test Start ---")

    # 1. 샘플 입력 데이터 생성 (역할은 Transcriber에서 온 것처럼 'TBD'로 설정)
    input_conversation = [
        DialogueTurn(role="TBD", content="Hello, how can I help you today?", chunk_index=0),
        DialogueTurn(role="TBD", content="Hi Doctor, I have a persistent cough and fever.", chunk_index=0),
        DialogueTurn(role="TBD", content="I see. How long have you had these symptoms?", chunk_index=0),
        DialogueTurn(role="TBD", content="About three days now.", chunk_index=0),
    ]

    # 2. LLM Handler의 _execute_prompt 함수를 Mocking으로 대체합니다.
    # @patch를 사용하여, 실제 함수가 아닌 우리가 만든 가짜 함수를 대신 사용하게 합니다.
    # NOTE: llm_service는 singleton 인스턴스입니다.
    with patch('backend.services.llm_handler.llm_service._execute_prompt', new=mock_execute_prompt):
        
        # 3. assign_roles 호출
        # 이 함수 내부에서 Mock 함수가 실행되고, 결과를 받아 Roles를 업데이트합니다.
        updated_turns = await role_service.assign_roles(input_conversation)
    
    # 4. 결과 검증 및 출력
    print("\n--- Test Result ---")
    print(f"Total Turns Processed: {len(updated_turns)}")
    
    # 예상 결과와 일치하는지 확인
    expected_roles = ["Doctor", "Patient", "Doctor", "Patient"]
    
    for i, turn in enumerate(updated_turns):
        print(f"[{i}] Role: {turn.role} (Expected: {expected_roles[i]}) | Content: {turn.content[:40]}...")
        assert turn.role == expected_roles[i], f"Assertion Failed: Turn {i} role is {turn.role}, expected {expected_roles[i]}"
        
    print("\n✅ All role assignments passed successfully!")

# ====================================================================
# 메인 실행
# ====================================================================

if __name__ == "__main__":
    # 비동기 함수를 실행하기 위해 asyncio.run() 사용
    try:
        asyncio.run(test_assign_roles_scenario())
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("경로 문제일 수 있습니다. 'backend.schemas' 및 'backend.services.role_service' 경로를 현재 실행 위치에 맞게 수정해주세요.")