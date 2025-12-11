import requests
import streamlit as st
from typing import Optional, Dict, Any

def get_api_base() -> str:
    """Dynamically fetch the API URL from session state."""
    # Strip trailing slash to avoid double slashes (http://url//ingest)
    url = st.session_state.get("api_url", "http://localhost:8000")
    return url.rstrip("/")

def poll_session_state(session_id: str):
    """
    Fetches the latest state from the backend.
    """
    api_base = get_api_base()
    
    try:
        # 1. Fetch Notifications
        notif_resp = requests.get(
            f"{api_base}/check_notifications", 
            params={"session_id": session_id},
            timeout=2 # Short timeout for polling
        )
        if notif_resp.status_code == 200:
            data = notif_resp.json()
            st.session_state.warnings = data.get("warnings", [])
            st.session_state.safety_alerts = data.get("safety_alerts", [])

    except Exception as e:
        # Don't spam the UI with errors if polling fails (server might be down)
        print(f"Polling Error: {e}")

def stop_session_api(session_id: str):
    """Signals backend to finalize session."""
    api_base = get_api_base()
    try:
        requests.post(f"{api_base}/stop_session", data={"session_id": session_id})
    except Exception as e:
        st.error(f"Failed to stop session: {e}")

def generate_document_api(session_id: str, task_type: str):
    """Triggers generation of derived documents (Referral/Certificate)."""
    api_base = get_api_base()
    try:
        payload = {
            "session_id": session_id,
            "dialogue_history": [], 
            "task_type": task_type
        }
        # Increase timeout for LLM generation
        resp = requests.post(f"{api_base}/generate_document", json=payload, timeout=60)
        
        if resp.status_code == 200:
            return resp.json().get("generated_summary")
        else:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None