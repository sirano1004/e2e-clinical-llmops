import streamlit as st

def setup_page():
    st.set_page_config(
        page_title="AI Clinical Scribe",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="auto"
    )
    st.title("🩺 Clinical Scribe Workspace")