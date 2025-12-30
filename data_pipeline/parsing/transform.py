from typing import Literal

from ..schema import ParsedHistoryTurn
from ..utils.normalization import normalize_text

from backend.schemas import SOAPNote

def max_chunk_index(history_list: list[dict]) -> int:
    if not history_list:
        return 0
    return max((t.get("chunk_index", 0) for t in history_list), default=0)

def get_empty_soap() -> dict:
    return SOAPNote().model_dump(mode="json")

def filter_soap_items(
    soap_data: dict,
    target_chunk_idx: int,
    mode: Literal["context", "target"] = "context",
) -> dict:
    if not isinstance(soap_data, dict):
        return get_empty_soap()

    filtered = get_empty_soap()
    for section in filtered.keys():
        for item in soap_data.get(section, []):
            if not isinstance(item, dict):
                continue
            src_idx = item.get("source_chunk_index", -1)
            if mode == "context" and src_idx < target_chunk_idx:
                filtered[section].append(item)
            elif mode == "target" and src_idx == target_chunk_idx:
                filtered[section].append(item)
    return filtered


def format_history_upto(history_list: list[dict], curr_idx: int) -> list[dict]:
    formatted_history = [
    ParsedHistoryTurn(
        role="user", 
        content=f"{(turn.get('role') or 'Speaker').upper()}: {turn.get('content', '')}"
    )
    for turn in history_list
    if turn.get("chunk_index", 0) <= curr_idx
]
    transcript = ". ".join([normalize_text(turn.get('content', '')) 
                  for turn in history_list 
                  if turn.get("chunk_index", 0) <= curr_idx
                ])

    return formatted_history, transcript