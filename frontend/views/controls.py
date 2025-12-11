# import streamlit as st
# from session_manager import reset_session
# from mock.mock_llm import mock_generate_note

# def render_audio_controls():
#     st.subheader("🎙️ Audio Controls")
#     status = st.session_state.recording_status
#     c1, c2, c3 = st.columns(3)
    
#     with c1: # Start/Pause
#         if status == "idle":
#             if st.button("▶️ Start", type="primary", use_container_width=True):
#                 st.session_state.recording_status = "recording"
#                 st.session_state.confirm_stop = False
#                 st.rerun()
#         elif status == "recording":
#             if st.button("⏸️ Pause", use_container_width=True):
#                 st.session_state.recording_status = "paused"
#                 st.rerun()
#         elif status == "paused":
#             if st.button("▶️ Resume", use_container_width=True):
#                 st.session_state.recording_status = "recording"
#                 st.rerun()

#     with c2: # Stop Logic
#         if status in ["recording", "paused"]:
#             if st.button("⏹️ Stop", use_container_width=True):
#                 st.session_state.confirm_stop = True
#                 st.rerun()
    
#     with c3: # Reset Logic
#             if st.button("🔄 Reset", use_container_width=True):
#                 reset_session()

#     # Stop Confirmation Dialog
#     if st.session_state.confirm_stop:
#         st.warning("⚠️ End session and generate notes?")
#         col_yes, col_no = st.columns(2)
#         if col_yes.button("✅ Yes, Generate", use_container_width=True):
#             st.session_state.recording_status = "idle"
#             st.session_state.confirm_stop = False
#             mock_generate_note() # Trigger generation service
#             st.rerun()
#         if col_no.button("❌ Cancel", use_container_width=True):
#             st.session_state.confirm_stop = False
#             st.rerun()

# def render_action_controls():
#     st.subheader("⚡ Quick Actions")
    
#     if st.session_state.soap_note:
#         c_edit, c_accept, c_reject = st.columns(3)
        
#         with c_edit:
#             if st.button("✏️ Edit", use_container_width=True, disabled=st.session_state.is_editing):
#                 st.session_state.is_editing = True
#                 st.rerun()
        
#         with c_accept:
#             if st.button("✅ Accept", use_container_width=True):
#                 st.session_state.is_editing = False
#                 st.toast("SOAP Note Accepted & Saved!")
#                 st.rerun()

#         with c_reject:
#             if st.button("❌ Reject", use_container_width=True):
#                 st.session_state.doctor_note = ""
#                 st.session_state.is_editing = False
#                 st.rerun()

#         st.divider()

#         c_ref, c_cert = st.columns(2)
#         with c_ref:
#             if st.button("✉️ Gen Referral", use_container_width=True):
#                 st.session_state.referral_letter = "Referral Letter Content..."
#                 st.toast("Referral Generated!")
#                 st.rerun()
#         with c_cert:
#             if st.button("📄 Gen Certificate", use_container_width=True):
#                 st.session_state.medical_certificate = "Medical Certificate Content..."
#                 st.toast("Certificate Generated!")
#                 st.rerun()
#     else:
#         st.caption("Finish recording to enable actions.")

import streamlit as st
from components.audio_recorder import render_audio_recorder
from api_client import poll_session_state, stop_session_api, generate_document_api
from session_manager import reset_session
import time

def render_audio_controls():
    st.subheader("🎙️ Audio Controls")
    
    # 1. Determine Mode
    mode = "local_mock" if st.session_state.use_mock_backend else "api"
    
    # 2. Render Component with Dynamic Settings
    render_audio_recorder(
        session_id=st.session_state.session_id,
        api_url=st.session_state.api_url,
        chunk_duration=st.session_state.chunk_duration, # <--- User Selected Seconds
        mode=mode # <--- Dependency Injection (Mock vs Real)
    )

    # 3. Status Info
    if mode == "local_mock":
        st.info(f"🛠️ **Mock Mode Active:** Audio chunks of {st.session_state.chunk_duration}s will be downloaded to your computer.")
    else:
        st.caption(f"📡 **Live Mode:** Streaming {st.session_state.chunk_duration}s chunks to API.")

    # 2. Polling Mechanism (To see updates on screen)
    # We add a "Refresh" button or use st_autorefresh if installed.
    # For MVP, a manual Refresh is safer to prevent UI glitches.
    col_poll, col_reset = st.columns([1, 1])
    
    with col_poll:
        if st.button("🔄 Refresh Data", use_container_width=True):
            poll_session_state(st.session_state.session_id)
            st.rerun()

    with col_reset:
        if st.button("🗑️ Reset Session", use_container_width=True):
             reset_session()

def render_action_controls():
    st.subheader("⚡ Quick Actions")
    
    # Document Generation Buttons
    # These now call the real API
    c_ref, c_cert = st.columns(2)
    
    with c_ref:
        if st.button("✉️ Gen Referral", use_container_width=True):
            with st.spinner("Generating Referral..."):
                content = generate_document_api(st.session_state.session_id, "referral")
                if content:
                    st.session_state.referral_letter = content
                    st.toast("Referral Generated!")
                    st.rerun()
    
    with c_cert:
        if st.button("📄 Gen Certificate", use_container_width=True):
            with st.spinner("Generating Certificate..."):
                content = generate_document_api(st.session_state.session_id, "certificate")
                if content:
                    st.session_state.medical_certificate = content
                    st.toast("Certificate Generated!")
                    st.rerun()