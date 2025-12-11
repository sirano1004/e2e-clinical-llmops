import streamlit as st

def render_transcript_view():
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