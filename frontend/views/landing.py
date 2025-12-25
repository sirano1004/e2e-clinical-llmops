import random
import string
import streamlit as st
from api_client import start_session_api

def generate_random_mrn():
    """Generate a random Medical Record Number (MRN)"""
    return ''.join(random.choices(string.digits, k=8))

def generate_random_doctor_id():
    """Generate a random Doctor ID"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def render_landing_page():
    st.title("🏥 Clinical LLMOps Platform")
    st.markdown("""
    Welcome to the Clinical LLMOps Platform! This application allows healthcare professionals to leverage
    large language models for clinical documentation and decision support.
    """)
    
    if st.button("🚀 Start New Session"):
        with st.spinner("Starting new session..."):
            doctor_id = generate_random_doctor_id()
            mrn = generate_random_mrn()
            response = start_session_api(doctor_id, mrn)
            
            if response is None:
                st.error("Failed to connect to the server. Please try again.")
            elif response.get("status") == "session_started":
                st.success(f"Session started successfully! Session ID: {response['session_id']}")
                st.session_state.session_id = response['session_id']
                st.rerun()
            else:
                st.error("Failed to start session. Please try again.")