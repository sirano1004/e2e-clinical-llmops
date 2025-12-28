import json

from typing import Tuple, Iterable
from pydantic import ValidationError

from .transform import max_chunk_index, format_history_upto, filter_soap_items
from ..utils.typing import validate_data
from ..config import settings
from ..schema import ParsedEntry
from backend.schemas import DialogueTurn, SOAPNote

def parse_and_validate_entry(line: str, strict: bool) -> Tuple[dict, dict, list[dict], dict, dict]:
    """
    Returns: (entry, input_context, history_list, chosen_json, rejected_json)
    Raises if strict and invalid.
    """
    entry = json.loads(line)
    session_id = entry.get("session_id")
    input_context = entry.get("input_context", {})

    if not session_id:
        if strict:
            raise ValueError("missing session_id")
        # lenient fallback (if ever needed)
        session_id = "unknown"

    # history
    try:
        raw_history_str = input_context.get("history", "[]")
        history_list_raw = json.loads(raw_history_str)
    except (json.JSONDecodeError, TypeError):
        history_list_raw = []
    history_list_raw = json.loads(raw_history_str)
    history_list = [validate_data(turn, DialogueTurn) for turn in history_list_raw]

    # chosen/rejected
    # Robus parsing
    def parse_soap_safe(field_name):
        raw_str = entry.get(field_name, "{}")
        try:
            return json.loads(raw_str)
        except (json.JSONDecodeError, TypeError):
            return {}
        
    chosen_json = validate_data(parse_soap_safe("chosen"), SOAPNote)
    rejected_json = validate_data(parse_soap_safe("rejected"), SOAPNote)

    return entry, input_context, history_list, chosen_json, rejected_json


def iter_parsed_records(
    entry: dict,
    input_context: dict,
    history_list: list[dict],
    chosen_json: dict,
    rejected_json: dict,
    existing_ids: set[str],
) -> Iterable[dict]:
    session_id = entry["session_id"]
    max_idx = max_chunk_index(history_list)

    for curr_idx in range(max_idx + 1):
        unique_id = f"{session_id}_{curr_idx}"
        if unique_id in existing_ids:
            yield None  # signal skip
            continue

        formatted_history = format_history_upto(history_list, curr_idx)

        prev_note_obj = filter_soap_items(chosen_json, curr_idx, mode="context")
        prev_note_rej_obj = filter_soap_items(rejected_json, curr_idx, mode="context")
        completion_obj = filter_soap_items(chosen_json, curr_idx, mode="target")
        completion_rej_obj = filter_soap_items(rejected_json, curr_idx, mode="target")

        try:
            parsed = ParsedEntry(
                id=unique_id,
                session_id=session_id,
                chunk_index=curr_idx,
                task_type=entry.get("task_type", "soap"),
                system_prompt=input_context.get("system_prompt", ""),
                history=formatted_history,
                previous_note=prev_note_obj,
                previous_note_rejected=prev_note_rej_obj,
                suffix_prompt=input_context.get("suffix_prompt", ""),
                completion=completion_obj,
                completion_rejected=completion_rej_obj,
                action=entry.get("action"),
                session_start=entry.get("session_start"),
                created_at=entry.get("_created_at"),
                data_pipeline_version=settings.data_pipeline_version,
            )
        except ValidationError as e:
            print("❌ ParsedEntry validation failed:", e)
            print("DETAILS:", e.errors()) 
            raise

        yield parsed.model_dump(mode="json")

