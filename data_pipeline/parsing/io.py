import os, json

def load_existing_ids(output_path: str) -> set[str]:
    ids: set[str] = set()
    if not os.path.exists(output_path):
        return ids

    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                if "id" in rec:
                    ids.add(rec["id"])
            except Exception:
                continue
    return ids
