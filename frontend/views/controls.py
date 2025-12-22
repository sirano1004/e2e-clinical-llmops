import streamlit as st
from components.audio_recorder import render_audio_recorder
from api_client import submit_feedback, generate_document_api, fetch_session_tasks
import time
import json

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
                    submit_feedback(
                        st.session_state.session_id, 
                        "accept"
                    )
                    st.rerun()

            with c_reject:
                if st.button("❌ Reject", use_container_width=True):
                    st.session_state.doctor_note = ""
                    st.session_state.note_status = "rejected"
                    submit_feedback(
                        st.session_state.session_id, 
                        "reject"
                    )
                    st.rerun()
    
    elif st.session_state.note_status == "editing":
        c_save, c_cancel = st.columns(2)
        
        with c_save:
            if st.button("💾 Save Changes", use_container_width=True, type="primary"):
                st.session_state.is_editing = False
                st.session_state.note_status = "edited"
                submit_feedback(
                    st.session_state.session_id, 
                    "edit",
                    edited_content=json.dumps(st.session_state.soap_note_buffer)
                )
                st.toast("✅ Changes Saved!")
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
                task_id = generate_document_api(st.session_state.session_id, "referral")
                if task_id is not None:
                    for _ in range(20):  # Max 20 attempts (10 seconds)
                        # 1. Check status (200 OK on success)
                        result = fetch_session_tasks(task_id)
                        status = result.get("status")  # PENDING, SUCCESS, FAILURE

                        # 2. Handle based on status
                        if status == "completed":
                            st.session_state.referral_letter = result.get("result").get("data")
                            st.toast("Referral Generated!")
                            st.rerun()
                            break  # Exit loop
                        
                        elif status == "failed":
                            st.error(f"Failed: {result.get('error')}")
                            break  # Exit loop
                        
                        elif status == "processing":
                            # Still processing -> do nothing and wait
                            pass 
                        
                        # 3. Wait 0.5 seconds then check again
                        time.sleep(0.5)
                    else:
                        st.error("Timeout: Taking too long.")
                    st.rerun()
    
    with c_cert:
        if st.button("📄 Gen Certificate", use_container_width=True):
            with st.spinner("Generating Certificate..."):
                task_id = generate_document_api(st.session_state.session_id, "certificate")
                if task_id is not None:
                    for _ in range(20):  # Max 20 attempts (10 seconds)
                        result = fetch_session_tasks(task_id)
                        status = result.get("status")
                        
                        if status == "completed":
                            st.session_state.medical_certificate = result.get("result").get("data")
                            st.toast("Certificate Generated!")
                            st.rerun()
                            break
                        
                        elif status == "failed":
                            st.error(f"Failed: {result.get('error')}")
                            break
                        
                        elif status == "processing":
                            pass  # Still processing
                        
                        time.sleep(0.5)
                    else:
                        st.error("Timeout: Taking too long.")
                    st.rerun()