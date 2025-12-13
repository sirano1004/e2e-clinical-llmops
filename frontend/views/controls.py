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

def render_action_controls():
    st.subheader("⚡ Quick Actions")

    if st.session_state.note_status == "pending":

        if st.session_state.soap_note:
            c_edit, c_accept, c_reject = st.columns(3)
            
            with c_edit:
                if st.button("✏️ Edit", use_container_width=True, disabled=st.session_state.is_editing):
                    st.session_state.is_editing = True
                    st.session_state.note_status = "editing"
                    st.rerun()
            
            with c_accept:
                if st.button("✅ Accept", use_container_width=True):
                    st.session_state.note_status = "accepted"
                    st.toast("SOAP Note Accepted & Saved!")
                    st.rerun()

            with c_reject:
                if st.button("❌ Reject", use_container_width=True):
                    st.session_state.doctor_note = ""
                    st.session_state.note_status = "rejected"
                    st.rerun()
    
    elif st.session_state.note_status == "editing":
        c_save, c_cancel = st.columns(2)
        
        with c_save:
            if st.button("💾 Save Changes", use_container_width=True, type="primary"):
                st.session_state.is_editing = False
                st.session_state.note_status = "edited"
                # 저장을 눌렀다고 해서 바로 Accept 처리를 할지, 다시 버튼을 보여줄지는 선택
                # 여기서는 다시 버튼을 보여주는 걸로 (Pending 유지)
                st.rerun()
        with c_cancel:
            if st.button("↩️ Cancel", use_container_width=True):
                st.session_state.is_editing = False
                st.session_state.note_status = "pending"
                st.rerun()        

    

        st.divider()
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