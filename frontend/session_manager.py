import uuid
import streamlit as st

def get_or_create_session_id() -> str:
    """
    Retrieves the current session ID or creates a new one if it doesn't exist.
    This ensures the session persists across Streamlit reruns.
    """
    # 1. Check if session_id exists in Streamlit's session state
    if "session_id" not in st.session_state:
        # Generate a unique UUID for the new consultation session
        new_id = str(uuid.uuid4())
        st.session_state.session_id = new_id
        
        # 2. Initialize State Variables
        # Chat History: Stores the dialogue between Doctor and Patient
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        # SOAP Note: Stores the structured clinical note (subjective, objective, etc.)
        if "soap_note" not in st.session_state:
            st.session_state.soap_note = {}
            
        # Warnings: Stores general quality warnings (e.g., potential hallucinations)
        if "warnings" not in st.session_state:
            st.session_state.warnings = []
            
        # Safety Alerts: Stores critical medical safety alerts (e.g., dosage errors)
        if "safety_alerts" not in st.session_state:
            st.session_state.safety_alerts = []

    return st.session_state.session_id

def init_session_state():
    """
    Initializes all session state variables required for the app.
    This function should be called at the start of the app.
    """
    # 1. Core Identity
    get_or_create_session_id()

    # 2. Chat & Note Data
    if "transcript" not in st.session_state:
        st.session_state.transcript = [
            {"role": "system", "content": "Session started. Ready to record."}
        ]
    
    if "doctor_note" not in st.session_state:
        st.session_state.doctor_note = ""

    # 3. App Status Flags
    if "recording_status" not in st.session_state:
        st.session_state.recording_status = "idle"  # Options: idle, recording, paused
    
    if "confirm_stop" not in st.session_state:
        st.session_state.confirm_stop = False

    # 4. Document Content (Referral / Certificate)
    if "referral_letter" not in st.session_state:
        st.session_state.referral_letter = ""
        
    if "medical_certificate" not in st.session_state:
        st.session_state.medical_certificate = ""
    
    if "is_editing" not in st.session_state:
        st.session_state.is_editing = False

def reset_session():
    """
    Resets the current session to start a fresh consultation.
    Clears all state variables and generates a new session ID.
    """
    # 1. Generate a new Session ID
    st.session_state.session_id = str(uuid.uuid4())
    
    # 2. Clear all data containers
    st.session_state.messages = []
    st.session_state.soap_note = {}
    st.session_state.warnings = []
    st.session_state.safety_alerts = []
    
    # Reset Data
    st.session_state.transcript = [{"role": "system", "content": "New session started."}]
    st.session_state.doctor_note = ""
    
    # Reset Flags
    st.session_state.recording_status = "idle"
    st.session_state.confirm_stop = False
    st.session_state.is_editing = False

    # Reset Documents
    st.session_state.referral_letter = ""
    st.session_state.medical_certificate = ""

    # Force Rerun
    st.rerun()

def save_note_callback():
    """
    Callback function triggered when Cmd+Enter is pressed in the text area.
    It saves the content (implicitly by Streamlit) and exits edit mode.
    """
    st.session_state.is_editing = False
    st.toast("✅ Note saved via shortcut!")