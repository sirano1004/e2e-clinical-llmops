import streamlit as st
from components.note_display import render_soap_note_view, render_soap_note_editor

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
                # Mode B: View
                warnings_map = {} 
                render_soap_note_view(st.session_state.soap_note, warnings_map)

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