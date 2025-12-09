import streamlit as st
import time

# --- Project Imports ---
# session_manager 모듈에서 함수들을 가져옵니다.
from session_manager import init_session_state, reset_session, save_note_callback
from components.note_display import render_soap_note_view, render_soap_note_editor

def mock_generate_note():
    """Simulate generating a note (Placeholder for testing)."""
    time.sleep(1)
    # Mock Response as a Dictionary (Structured)
    st.session_state.soap_note = {
        "subjective": [
            {"text": "Patient reports persistent headache for 3 days.", "source_chunk_index": 0},
            {"text": "Pain rated 6/10.", "source_chunk_index": 1}
        ],
        "objective": [
            {"text": "BP 120/80.", "source_chunk_index": 2}
        ],
        "assessment": [
            {"text": "Tension headache.", "source_chunk_index": 2}
        ],
        "plan": [
            {"text": "Rest and hydration.", "source_chunk_index": 3}
        ]
    }

def main():
    # 1. Page Config
    st.set_page_config(
        page_title="AI Clinical Scribe",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 2. Initialize Session (Load from session_manager.py)
    init_session_state()
    
    # --- Sidebar ---
    with st.sidebar:
        st.title("Settings")
        st.write(f"Session ID: `{st.session_state.session_id[:8]}...`")
        
        st.divider()
        
        # Layout Adjustment
        st.subheader("🖥️ Layout")
        split_ratio = st.slider("Split View Ratio", 0.2, 0.8, 0.5, 0.05)
        
        st.divider()
        st.caption("v1.0.2 - Split View Mode")

    # --- Main Layout ---
    col1_width = split_ratio
    col2_width = 1.0 - split_ratio
    
    st.markdown("#### 🩺 Clinical Scribe Workspace")

    col_chat, col_note = st.columns([col1_width, col2_width])

    # LEFT: Conversation
    with col_chat:
        st.info("💬 **Live Transcript**")
        with st.container(height=500, border=True):
            for msg in st.session_state.transcript:
                role = msg["role"]
                content = msg["content"]
                
                if role == "system":
                    st.caption(f"🔧 {content}")
                else:
                    st.chat_message(role).write(content)
            
            if st.session_state.recording_status == "recording":
                st.write("🔴 *Recording...*")

    # RIGHT: Notes & Docs
    with col_note:
        st.success("📝 **Clinical Documents**")
        tab1, tab2, tab3 = st.tabs(["🩺 SOAP Note", "✉️ Referral", "📄 Certificate"])

        # Tab 1: SOAP Note
        with tab1:
            with st.container(height=500, border=True):
                
                # [Mode A] Edit Mode (Structured Data Editor)
                if st.session_state.is_editing:
                    # 💡 [핵심] 딕셔너리를 넣고, 수정된 딕셔너리를 바로 받습니다.
                    # String Parsing 과정이 완전히 사라집니다!
                    updated_soap_dict = render_soap_note_editor(st.session_state.soap_note)
                    
                    # 실시간 반영을 위해 임시 저장 (Accept 누르기 전까지)
                    st.session_state.soap_note_buffer = updated_soap_dict
                    
                # [Mode B] View Mode (Highlights)
                else:
                    warnings_map = {} # (Mock for now)
                    render_soap_note_view(st.session_state.soap_note, warnings_map)

        # # Tab 1: SOAP Note
        # with tab1:
        #     with st.container(height=500, border=True):
                
        #         # [Logic A] Edit Mode: Show Text Area (String)
        #         if st.session_state.is_editing:
        #             # Convert Dict -> String for editing
        #             initial_text = soap_dict_to_string(st.session_state.soap_note)
                    
        #             st.text_area(
        #                 "Edit Note",
        #                 value=initial_text,
        #                 height=480,
        #                 key="soap_note_edit_buffer", # Temporary buffer
        #                 label_visibility="collapsed",
        #                 on_change=save_note_callback
        #             )
                    
        #         # [Logic B] View Mode: Show Structured Highlights (Dict)
        #         else:
        #             # Fetch warnings from session state (or API)
        #             warnings_map = {
        #                 # Mockup: In real app, get this from st.session_state.warnings
        #                 # '0': {'warnings': ['Hallucination detected']} 
        #             }
                    
        #             # Render nice UI with red-lines
        #             render_soap_note_view(st.session_state.soap_note, warnings_map)

        
        # Tab 2: Referral
        with tab2:
            with st.container(height=500, border=True):
                if st.session_state.referral_letter:
                    st.text_area("Referral", value=st.session_state.referral_letter, height=480)
                else:
                    st.info("Referral not generated yet.")

        # Tab 3: Certificate
        with tab3:
            with st.container(height=500, border=True):
                if st.session_state.medical_certificate:
                    st.text_area("Certificate", value=st.session_state.medical_certificate, height=480)
                else:
                    st.info("Certificate not generated yet.")

    # --- Bottom Controls ---
    st.divider()
    col_rec, col_actions = st.columns([1, 1])
    
    # Audio Controls
    with col_rec:
        st.subheader("🎙️ Audio Controls")
        status = st.session_state.recording_status
        c1, c2, c3 = st.columns(3)
        
        with c1: # Start/Pause
            if status == "idle":
                if st.button("▶️ Start", type="primary", use_container_width=True):
                    st.session_state.recording_status = "recording"
                    st.session_state.confirm_stop = False
                    st.rerun()
            elif status == "recording":
                if st.button("⏸️ Pause", use_container_width=True):
                    st.session_state.recording_status = "paused"
                    st.rerun()
            elif status == "paused":
                if st.button("▶️ Resume", use_container_width=True):
                    st.session_state.recording_status = "recording"
                    st.rerun()

        with c2: # Stop Logic
            if status in ["recording", "paused"]:
                if st.button("⏹️ Stop", use_container_width=True):
                    st.session_state.confirm_stop = True
                    st.rerun()
        
        with c3: # Reset Logic
             if st.button("🔄 Reset", use_container_width=True):
                 reset_session()

        # Stop Confirmation Dialog
        if st.session_state.confirm_stop:
            st.warning("⚠️ End session and generate notes?")
            col_yes, col_no = st.columns(2)
            if col_yes.button("✅ Yes, Generate", use_container_width=True):
                st.session_state.recording_status = "idle"
                st.session_state.confirm_stop = False
                mock_generate_note() # Trigger generation
                st.rerun()
            if col_no.button("❌ Cancel", use_container_width=True):
                st.session_state.confirm_stop = False
                st.rerun()

    # Document Actions
    with col_actions:
        st.subheader("⚡ Quick Actions")
        
        if st.session_state.soap_note:
            # --- Feedback Buttons (Edit / Accept / Reject) ---
            c_edit, c_accept, c_reject = st.columns(3)
            
            with c_edit:
                # Button to enable editing mode
                if st.button("✏️ Edit", use_container_width=True, disabled=st.session_state.is_editing):
                    st.session_state.is_editing = True
                    st.rerun()
            
            with c_accept:
                # Button to finalize/save and disable editing
                if st.button("✅ Accept", use_container_width=True):
                    st.session_state.is_editing = False # Lock the text area
                    st.toast("SOAP Note Accepted & Saved!")
                    st.rerun()

            with c_reject:
                # Button to clear or reject the note
                if st.button("❌ Reject", use_container_width=True):
                    st.session_state.doctor_note = "" # Clear the note
                    st.session_state.is_editing = False
                    st.rerun()

            st.divider() # Visual separation

            # --- Generation Buttons (Referral / Certificate) ---
            # Only show these if the note is accepted (optional, but good UX)
            c_ref, c_cert = st.columns(2)
            with c_ref:
                if st.button("✉️ Gen Referral", use_container_width=True):
                    st.session_state.referral_letter = "Referral Letter Content..."
                    st.toast("Referral Generated!")
                    st.rerun()
            with c_cert:
                if st.button("📄 Gen Certificate", use_container_width=True):
                    st.session_state.medical_certificate = "Medical Certificate Content..."
                    st.toast("Certificate Generated!")
                    st.rerun()
        else:
            st.caption("Finish recording to enable actions.")

if __name__ == "__main__":
    main()