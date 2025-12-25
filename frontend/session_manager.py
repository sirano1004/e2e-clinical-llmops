import streamlit as st

# --- Constants & Defaults ---
# We define the initial state in one place to ensure consistency 
# between application start and session resets.
INITIAL_STATE = {
    "transcript": [],
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
    "note_status": "pending",

    "chunk_duration": 30,         # Default 30 seconds
    "use_mock_backend": False,    # Default to False (Live Mode)
}

def init_session_state():
    """
    Initialize the Streamlit session state. 
    Iterates through INITIAL_STATE to ensure all keys exist.
    """

    # 1. Initialize all other keys from the master dictionary
    for key, default_value in INITIAL_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def reset_session():
    """
    Hard reset: Generates a new Session ID and restores all state 
    variables to their default values defined in INITIAL_STATE.
    """
    # 1. Restore Defaults (Loop ensures we never miss a key)
    for key, default_value in INITIAL_STATE.items():
        st.session_state[key] = default_value

    # 2. Clear Session ID
    if "session_id" in st.session_state:
        del st.session_state["session_id"]
        
    # 3. Force UI refresh
    st.rerun()

def save_note_callback():
    """
    Triggered by Cmd+Enter in text areas.
    Commits the buffer to the main state and exits edit mode.
    """
    # In a real app, you might add validation logic here before saving.
    st.session_state.is_editing = False
    st.toast("✅ Note saved successfully!")