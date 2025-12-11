import time
import streamlit as st

def mock_generate_note():
    """Simulate generating a note."""
    time.sleep(1)
    st.session_state.soap_note = {
        "subjective": [
            {"text": "Patient reports persistent headache for 3 days.", "source_chunk_index": 0},
            {"text": "Pain rated 6/10.", "source_chunk_index": 1}
        ],
        "objective": [{"text": "BP 120/80.", "source_chunk_index": 2}],
        "assessment": [{"text": "Tension headache.", "source_chunk_index": 2}],
        "plan": [{"text": "Rest and hydration.", "source_chunk_index": 3}]
    }