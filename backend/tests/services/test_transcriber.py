import os
import pytest
from backend.services.transcriber import transcriber_service

# 1. Setup path for the test audio file
AUDIO_PATH = "test_data/CAR0001.mp3"

@pytest.mark.skipif(not os.path.exists(AUDIO_PATH), reason="Skipped because local test_data/CAR0001.mp3 file is missing.")
def test_transcribe_audio_real_file():
    """
    Integration test to verify WhisperX runs correctly with a real audio file.
    """
    print(f"\n🎧 Testing with file: {AUDIO_PATH}")
    
    # Execution (Action)
    result = transcriber_service.transcribe_audio(AUDIO_PATH)
    
    # Verification (Assert)
    # 1. Verify that text is not empty
    assert result["text"] is not None
    assert len(result["text"]) > 0
    
    # 2. Verify structure (must contain 'conversation' list)
    assert "conversation" in result
    assert isinstance(result["conversation"], list)
    
    # 3. Verify Speaker Diarization (Optional check)
    # If Diarization is active, role should be 'SPEAKER_XX' or 'UNKNOWN'
    first_turn = result["conversation"][0]
    print(f"\n🗣️ Detected Speaker: {first_turn.role}")
    print(f"📝 Content: {first_turn.content}")
    
    # Verify Pydantic model attributes
    assert hasattr(first_turn, "role")
    assert hasattr(first_turn, "content")

def test_transcriber_initialization():
    """
    Unit test to verify the model loaded successfully.
    """
    assert transcriber_service.model is not None
    
    # Verify device (Should be 'mps' or 'cpu' on Mac, 'cuda' on Colab)
    print(f"\n⚙️ Running on device: {transcriber_service.device}")
    assert transcriber_service.device in ["cuda", "mps", "cpu"]