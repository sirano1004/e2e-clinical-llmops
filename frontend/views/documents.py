import streamlit as st
from components.note_display import render_soap_note_view, render_soap_note_editor
from mock.mock_llm import mock_generate_note
from api_client import fetch_soap_note, fetch_warnings

@st.fragment(run_every=1)
def live_render_soap_note():
    """
    Live rendering of the SOAP note area.
    Polls the backend independently every second.
    """
    warnings_map = {} 
    if st.session_state.use_mock_backend:
        mock_generate_note()
        warnings_map = {0: ["Mock Warning: Review subjective section."],
                        2: ["Mock Warning: Check assessment accuracy."]}
    else:
        soap_note = fetch_soap_note(st.session_state.session_id)
        if soap_note:
            st.session_state.soap_note = soap_note
        warnings_response = fetch_warnings(st.session_state.session_id)
        # warnings_response가 None이거나 비어있을 경우 대비
        if warnings_response:
            raw_warnings_list = warnings_response.get("warnings", [])
            for w in raw_warnings_list:
                c_idx = int(w.get("chunk_index"))
                msgs = w.get("warnings", [])
                
                # chunk_index가 유효하고 메시지가 있는 경우만 맵에 등록
                if c_idx is not None and msgs:
                    warnings_map[c_idx] = msgs

    render_soap_note_view(st.session_state.soap_note, warnings_map)

def render_documents_view():
    st.success("📝 **Clinical Documents**")
    tab1, tab2, tab3 = st.tabs(["🩺 SOAP Note", "✉️ Referral", "📄 Certificate"])

    # Tab 1: SOAP Note
    with tab1:
        with st.container(height=500, border=True):
            if st.session_state.is_editing:
                # Mode A: Edit
                updated_soap_dict = render_soap_note_editor(st.session_state.soap_note)
                st.session_state.soap_note_buffer = updated_soap_dict
            else:
                live_render_soap_note()

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