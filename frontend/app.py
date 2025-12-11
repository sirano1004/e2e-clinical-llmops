import streamlit as st
import time

# --- Project Views ---
from views.sidebar import side_bar
from views.page import setup_page
from views.transcript import render_transcript_view
from views.documents import render_documents_view
from views.controls import render_audio_controls, render_action_controls

# --- Project Imports ---
from session_manager import init_session_state, reset_session, save_note_callback
from components.note_display import render_soap_note_view, render_soap_note_editor


def main():
    # 1. Setup
    setup_page()
    init_session_state()
    side_bar()

    # 2. Main Layout (Grid System)
    col_chat, col_note = st.columns(2)

    with col_chat:
        render_transcript_view()

    with col_note:
        render_documents_view()

    # 3. Bottom Controls
    st.divider()
    col_rec, col_actions = st.columns(2)
    
    with col_rec:
        render_audio_controls()
    
    with col_actions:
        render_action_controls()

if __name__ == "__main__":
    main()