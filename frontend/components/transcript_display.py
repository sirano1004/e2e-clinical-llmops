import streamlit as st

def render_live_transcript(segments):
    """
    Renders the SegmentInfo structure (List[dict]) from backend/schemas.py
    as a Streamlit chat UI.
    """
    # If no data, show info message
    if not segments:
        st.info("Waiting... Please start speaking.")
        return

    # Loop through segments
    for seg in segments:
        # 1. Check speaker name (comes as 'speaker' key from backend)
        speaker_role = seg.get("speaker", "TBD")
        
        # 2. Map icon/name and alignment
        if speaker_role == "Doctor":
            alignment = "assistant"  # Left-aligned
            avatar = "👨‍⚕️"
            role_name = "Doctor"
            # bg_color = "rgba(255, 75, 75, 0.1)"  # Doctor with slight red tone (optional)
        else:
            alignment = "user"  # Right-aligned
            avatar = "👤"
            role_name = "Patient"
            # bg_color = "transparent"

        # 3. Assemble markdown text (Rich Text)
        # Loop through words list and check 'is_unclear' flag
        markdown_parts = []
        words = seg.get("words", [])
        
        for w in words:
            word_text = w.get("word", "")
            if w.get("is_unclear", False):
                # Use warning/red styling to highlight uncertain words
                markdown_parts.append(f":red[{word_text}]")
            else:
                markdown_parts.append(word_text)
        
        full_text = " ".join(markdown_parts)

        # 4. Draw speech bubble
        with st.chat_message(alignment, avatar=avatar):
            st.markdown(f"**{role_name}:** {full_text}")
            # (Optional) Debugging time display
            # st.caption(f"{seg['start']:.1f}s - {seg['end']:.1f}s")