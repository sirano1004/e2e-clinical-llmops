import os, json

from ..config import settings
from .io import load_existing_ids
from .parse import parse_and_validate_entry, iter_parsed_records

def process_file(filename: str, strict: bool = True) -> None:
    input_path = os.path.join(settings.data_dir, settings.raw_data_dir, filename)
    output_path = os.path.join(settings.data_dir, settings.parsed_data_dir, filename)

    print(f"Input path: {input_path}")
    print(f"Output path: {output_path}")

    if not os.path.exists(input_path):
        print(f"⏩ Skipped: file does not exist ({filename})")
        return

    existing_ids = load_existing_ids(output_path)
    print(f"   ㄴ Found {len(existing_ids)} existing records")

    success = skip = fail = filter = 0

    with open(input_path, "r", encoding="utf-8") as fin, open(output_path, "a", encoding="utf-8") as fout:
        for line in fin:
            try:
                entry, input_context, history_list, chosen_json, rejected_json = parse_and_validate_entry(line, strict=strict)

                # Length filter
                history_total_length = sum(len(turn.get('content', '')) for turn in history_list)
                soap_note_total_length = sum(len(item.get('text', '')) for _, v in chosen_json.items() for item in v)

                if history_total_length <= 0:
                    filter += 1
                    continue

                ratio = soap_note_total_length / history_total_length

                drop_reason = None

                if history_total_length <= settings.min_length:
                    drop_reason = "transcript_too_short"

                elif ratio <= settings.min_ratio:
                    drop_reason = "soap_too_sparse"

                elif ratio >= settings.max_ratio:
                    drop_reason = "soap_too_similar"

                if drop_reason:
                    filter += 1
                    # optional: metadata / log
                    # record["drop_reason"] = drop_reason
                    continue

                for rec in iter_parsed_records(entry, input_context, history_list, chosen_json, rejected_json, existing_ids):
                    if rec is None:
                        skip += 1
                        continue
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    existing_ids.add(rec["id"])
                    success += 1

            except Exception as e:
                fail += 1
                if strict:
                    # strict mode: just drop this entry; keep going
                    continue
                print(f"❌ Line error ({filename}): {e}")

    print(f"✅ Done: added {success}, skipped {skip}, failed {fail}, filtered {filter}")
