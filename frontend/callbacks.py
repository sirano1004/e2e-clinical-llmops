# frontend/callbacks.py
import streamlit as st
import time

def save_note_callback():
    """
    Callback function triggered when Cmd+Enter is pressed in the text area.
    It saves the content (implicitly by Streamlit) and exits edit mode.
    """
    st.session_state.is_editing = False
    st.toast("✅ Note saved via shortcut!")

def mock_generate_note():
    time.sleep(1)
    st.session_state.doctor_note = """Subjective:
Patient reports persistent headache (3 days).

Objective:
BP 120/80.

Assessment:
Tension headache.

Plan:
Rest and hydration.
"""