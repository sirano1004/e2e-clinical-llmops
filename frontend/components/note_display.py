import streamlit as st
from styles import NOTE_STYLES


def render_soap_note_view(soap_note, warnings_map):
    """
    [View Mode] Renders the SOAP note with highlights based on chunk_index.
    soap_note: Dict containing lists of items (with source_chunk_index).
    warnings_map: Dict {chunk_index: [warning_msgs]}
    """
    if not soap_note:
        st.info("No notes generated yet.")
        return

    st.markdown(NOTE_STYLES, unsafe_allow_html=True)

    # Iterate strictly through standard SOAP sections
    for section in ["subjective", "objective", "assessment", "plan"]:
        items = soap_note.get(section, [])
        if not items:
            continue

        st.markdown(f"<div class='note-header'>{section.capitalize()}</div>", unsafe_allow_html=True)

        for item in items:
            # item structure: {'text': '...', 'source_chunk_index': 0}
            text = item.get("text", "")
            chunk_idx = item.get("source_chunk_index", -1)

            chunk_warnings = warnings_map.get(str(chunk_idx), [])

            if chunk_warnings:
                warning_msg = " | ".join(chunk_warnings["warnings"])
                st.markdown(
                    f"<div class='note-warning'><span class='note-warning-title'>Warning:</span>{text}<br>{warning_msg}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"<p class='note-item'>- {text}</p>", unsafe_allow_html=True)

        st.markdown("<div class='note-divider'></div>", unsafe_allow_html=True)


def render_soap_note_editor(soap_note):
    """
    [Edit Mode] Renders editable tables for each SOAP section.
    Returns the updated SOAP note dictionary structure.
    """
    updated_note = {}
    
    st.info("✏️ Edit specific items. Add new rows if needed.")

    # Create a data editor for each section.
    for section in ["subjective", "objective", "assessment", "plan"]:
        st.markdown(f"**{section.capitalize()}**")
        
        # 1. Fetch the item list for the current section
        items = soap_note.get(section, [])
        
        # 2. Show in the Data Editor (list of dicts -> table-like UI)
        # num_rows="dynamic": allow adding/removing rows
        edited_items = st.data_editor(
            items,
            column_config={
                "text": st.column_config.TextColumn(
                    "Clinical Fact", 
                    width="large",
                    required=True
                ),
                # Key: hide ID and chunk index columns
                # Users edit only the text, IDs remain in the data
                "id": None,
                "source_chunk_index": None
            },
            num_rows="fixed", 
            key=f"editor_{section}",
            use_container_width=True,
            hide_index=True
        )
        
        # 3. Store the edited data in the result dictionary
        updated_note[section] = edited_items
        
    return updated_note
