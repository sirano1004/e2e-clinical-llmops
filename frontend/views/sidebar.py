# sidebar.py
import os
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


def _default_api_url() -> str:
    return os.environ.get("API_URL", "http://localhost:8002")


def _ensure_state() -> None:
    if "api_url" not in st.session_state:
        st.session_state.api_url = _default_api_url()


def _set_api_url(api_url: str) -> None:
    cleaned = api_url.strip()
    if not cleaned:
        st.warning("API URL cannot be empty; keeping the previous value.")
        return

    st.session_state.api_url = cleaned
    os.environ["API_URL"] = cleaned
    st.toast(f"API URL updated to {cleaned}")


def side_bar() -> None:
    _ensure_state()

    with st.sidebar:
        st.title("Settings")

        st.subheader("🔌 Backend API")

        # 1. API Configuration
        default_url = _default_api_url()
        api_url_input = st.text_input(
            "API base URL",
            value=st.session_state.api_url,
            key="api_url_input",
            help="Overrides the default pulled from frontend/.env (API_URL).",
            placeholder=default_url,
        )

        col_apply, col_reset = st.columns(2)
        with col_apply:
            if st.button("Apply", use_container_width=True):
                _set_api_url(api_url_input)

        with col_reset:
            if st.button("Reset to .env", use_container_width=True):
                _set_api_url(default_url)

        st.info(f"Active API target: {st.session_state.api_url}")

        # 2. Chunking Logic
        st.number_input(
            "Chunk Duration (sec)",
            min_value=5,
            max_value=60,
            value=30,
            step=5,
            key="chunk_duration",
            help="How often to slice audio and process it."
        )
        
        # 3. Developer Mode (Dependency Injection)
        st.checkbox(
            "🛠️ Mock Backend (Save Locally)",
            key="use_mock_backend",
            help="If checked, audio chunks are saved to your local 'debug_chunks' folder instead of sent to the API."
        )
        st.divider()
        if st.button("🔄 Reset Session", use_container_width=True):
            from session_manager import reset_session
            reset_session()