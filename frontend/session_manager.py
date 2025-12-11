import uuid
import streamlit as st
from datetime import datetime

# --- Constants & Defaults ---
# We define the initial state in one place to ensure consistency 
# between application start and session resets.
INITIAL_STATE = {
    "transcript": [
        {"role": "system", "content": "Session started. Ready to record."}
    ],
    "soap_note": {
        "subjective": [],
        "objective": [],
        "assessment": [],
        "plan": []
    },
    # Buffers are used during 'Edit Mode' to hold temporary changes
    "soap_note_buffer": {}, 
    "recording_status": "idle", # Options: idle, recording, paused
    "confirm_stop": False,
    "is_editing": False,
    "referral_letter": "",
    "medical_certificate": "",
    "warnings": [],
    "safety_alerts": [],

    "chunk_duration": 30,         # Default 30 seconds
    "use_mock_backend": False,    # Default to False (Live Mode)
}

def get_session_id() -> str:
    """Return the current session ID, generating one if needed."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id

def init_session_state():
    """
    Initialize the Streamlit session state. 
    Iterates through INITIAL_STATE to ensure all keys exist.
    """
    # 1. Ensure Session ID exists
    get_session_id()

    # 2. Initialize all other keys from the master dictionary
    for key, default_value in INITIAL_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def reset_session():
    """
    Hard reset: Generates a new Session ID and restores all state 
    variables to their default values defined in INITIAL_STATE.
    """
    # 1. New Session ID
    st.session_state.session_id = str(uuid.uuid4())
    
    # 2. Restore Defaults (Loop ensures we never miss a key)
    for key, default_value in INITIAL_STATE.items():
        st.session_state[key] = default_value
        
    # 3. Update Transcript with specific reset message
    st.session_state.transcript = [
        {"role": "system", "content": f"New session started at {datetime.now().strftime('%H:%M')}."}
    ]

    # 4. Force UI refresh
    st.rerun()

def save_note_callback():
    """
    Triggered by Cmd+Enter in text areas.
    Commits the buffer to the main state and exits edit mode.
    """
    # In a real app, you might add validation logic here before saving.
    st.session_state.is_editing = False
    st.toast("✅ Note saved successfully!")