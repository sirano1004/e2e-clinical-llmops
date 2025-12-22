import streamlit as st
from components.transcript_display import render_live_transcript
from api_client import fetch_transcript_data
from mock.mock_llm import mock_generate_transcript

# 💡 Use @st.fragment to isolate this part of the UI.
# 'run_every=1' automatically re-runs this function every 1 second
# without reloading the entire page or resetting the editor.
@st.fragment(run_every=1)
def render_transcript_view():
    """
    Renders the live transcript area. 
    Polls the backend independently if recording is active.
    """
    st.info("💬 **Live Transcript**")
    
    with st.container(height=500, border=True):
        if st.session_state.use_mock_backend:
            mock_generate_transcript()
        else:
            transcript = fetch_transcript_data(st.session_state.session_id)

            if transcript:
                st.session_state.transcript = transcript

        if st.session_state.transcript:
            # Fetch fresh segments from backend              
            render_live_transcript(st.session_state.transcript)
        else:
            st.caption("🎧 Listening...")