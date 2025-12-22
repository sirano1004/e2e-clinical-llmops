import requests
import streamlit as st

def get_api_base() -> str:
    """Dynamically fetch the API URL from session state."""
    # Strip trailing slash to avoid double slashes (http://url//ingest)
    url = st.session_state.get("api_url", "http://localhost:8000")
    return url.rstrip("/")

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
            "task_type": task_type
        }
        # Increase timeout for LLM generation
        resp = requests.post(f"{api_base}/generate_document", params=payload, timeout=60)
        
        if resp.status_code == 202:
            if resp.json().get("status") == "queued":
                st.toast(resp.json().get("message", "Task queued."))
                return resp.json().get("task_id")
            else:
                st.error("Failed to queue document generation.")
                return None
        else:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def fetch_transcript_data(session_id: str):

    api_base = get_api_base()
    try:
        resp = requests.get(f"{api_base}/get_transcript", params={"session_id": session_id})
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
            return []
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return []

def fetch_soap_note(session_id: str):
    api_base = get_api_base()
    try:
        resp = requests.get(f"{api_base}/get_soap_note", params={"session_id": session_id})
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
            return {}
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return {}
    
def fetch_warnings(session_id: str):
    api_base = get_api_base()
    try:
        resp = requests.get(f"{api_base}/check_notifications", params={"session_id": session_id})
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
            return {
                "warnings": [],
                "safety_alerts": []
            }
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return {
                "warnings": [],
                "safety_alerts": []
            }

def fetch_session_tasks(task_ids: str):
    api_base = get_api_base()
    try:
        resp = requests.get(f"{api_base}/task_status/{task_ids}")
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
            return {}
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return {}

def submit_feedback(session_id: str, feedback_type: str, edited_content: str = "{}"):
    api_base = get_api_base()
    try:
        payload = {
            "session_id": session_id,
            "feedback_type": feedback_type,
            "edited_content": edited_content
        }
        resp = requests.post(f"{api_base}/submit_feedback", data=payload)
        if resp.status_code == 200:
            st.success("Feedback submitted successfully.")
        else:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
    except Exception as e:
        st.error(f"Connection Error: {e}")