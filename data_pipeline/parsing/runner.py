import os, json

from ..config import settings
from .io import load_existing_ids
from .parse import parse_and_validate_entry, iter_parsed_records

def process_file(filename: str, strict: bool = True) -> None:
    input_path = os.path.join(settings.data_dir, settings.raw_data_dir, filename)
    output_path = os.path.join(settings.data_dir, settings.parsed_data_dir, filename)

    print(f"입력 경로: {input_path}")
    print(f"출력 경로: {output_path}")

    if not os.path.exists(input_path):
        print(f"⏩ 스킵: 파일이 없습니다 ({filename})")
        return

    existing_ids = load_existing_ids(output_path)
    print(f"   ㄴ 기존 데이터: {len(existing_ids)}건 발견")

    success = skip = fail = 0

    with open(input_path, "r", encoding="utf-8") as fin, open(output_path, "a", encoding="utf-8") as fout:
        for line in fin:
            try:
                entry, input_context, history_list, chosen_json, rejected_json = parse_and_validate_entry(line, strict=strict)

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
                print(f"❌ 라인 에러 ({filename}): {e}")

    print(f"✅ 완료: 신규 추가 {success}건, 중복 스킵 {skip}건, 실패 {fail}건")
