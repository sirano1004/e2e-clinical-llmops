import json
import os
import glob
from typing import List, Dict, Any
from datasets import Dataset

# --- Path Configuration ---
# Adjust paths as needed based on your project structure
from ..config import settings

def format_conversation(
    system_prompt: str,
    history: List[Dict[str, Any]],
    suffix_template: str,
    context_note: Dict[str, Any],
    completion: Dict[str, Any] = None,
    include_assistant: bool = True
) -> List[Dict[str, str]]:
    """
    Constructs the conversation list based on the specific logic provided.
    
    Structure:
    1. System Prompt
    2. History (cleaned, no chunk_index)
    3. User Prompt (Suffix with Context Note injected)
    4. Assistant Response (Completion JSON) - Optional
    """
    
    messages = []
    
    # 1. System Prompt
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    
    # 2. History (Remove 'chunk_index' cleanly)
    # We reconstruct the dict to ensure only 'role' and 'content' exist
    for turn in history:
        messages.append({
            'role': turn['role'],
            'content': turn['content']
        })
    
    # 3. User Prompt (Suffix + Context Injection)
    # Dump context note to string
    context_str = json.dumps(context_note, indent=2, ensure_ascii=False)
    
    # Replace placeholder
    # Safety check: if placeholder is missing, just append
    if "[NOTE_CONTEXT]" in suffix_template:
        user_content = suffix_template.replace("[NOTE_CONTEXT]", context_str)
    else:
        # Fallback if template is weird
        user_content = f"{suffix_template}\n\nContext:\n{context_str}"
        
    messages.append({'role': 'user', 'content': user_content})
    
    # 4. Assistant Response (Completion)
    if include_assistant and completion:
        assistant_content = json.dumps(completion, indent=2, ensure_ascii=False)
        messages.append({'role': 'assistant', 'content': assistant_content})
        
    return messages

def process_sft_data(input_files: List[str]) -> Dataset:
    """
    Reads SFT JSONL files and converts to HF Dataset with 'messages' column.
    """
    data_list = []
    
    print(f"🔄 Formatting SFT Data from {len(input_files)} files...")
    
    for file_path in input_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                item = json.loads(line)
                
                # Construct Messages
                try:
                    messages = format_conversation(
                        system_prompt=item.get('system_prompt', ""),
                        history=item.get('history', []),
                        suffix_template=item.get('suffix_prompt', ""),
                        context_note=item.get('previous_note', {}),
                        completion=item.get('completion', {}),
                        include_assistant=True
                    )
                    
                    data_list.append({"messages": messages})
                except Exception as e:
                    print(f"⚠️ Error formatting SFT item: {e}")
                    continue

    return Dataset.from_list(data_list)

def process_dpo_data(input_files: List[str]) -> Dataset:
    """
    Reads DPO JSONL files and converts to HF Dataset with 'chosen' and 'rejected' columns.
    Expected format for TRL:
      - chosen: List[Dict] (Full conversation)
      - rejected: List[Dict] (Full conversation)
    """
    data_list = []
    
    print(f"🔄 Formatting DPO Data from {len(input_files)} files...")
    
    for file_path in input_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                item = json.loads(line)
                
                try:
                    # 1. Chosen (Positive Sample)
                    # Uses 'previous_note' and 'completion'
                    chosen_messages = format_conversation(
                        system_prompt=item.get('system_prompt', ""),
                        history=item.get('history', []),
                        suffix_template=item.get('suffix_prompt', ""),
                        context_note=item.get('previous_note', {}),
                        completion=item.get('completion', {}),
                        include_assistant=True
                    )
                    
                    # 2. Rejected (Negative Sample)
                    # Uses 'previous_note_rejected' and 'completion_rejected'
                    # Note: If 'previous_note_rejected' is missing, fallback to 'previous_note'
                    rej_note = item.get('previous_note_rejected') or item.get('previous_note', {})
                    rej_completion = item.get('completion_rejected', {})
                    
                    rejected_messages = format_conversation(
                        system_prompt=item.get('system_prompt', ""),
                        history=item.get('history', []),
                        suffix_template=item.get('suffix_prompt', ""),
                        context_note=rej_note,
                        completion=rej_completion,
                        include_assistant=True
                    )
                    
                    data_list.append({
                        "chosen": chosen_messages,
                        "rejected": rejected_messages
                    })
                    
                except Exception as e:
                    print(f"⚠️ Error formatting DPO item: {e}")
                    continue

    return Dataset.from_list(data_list)

def main():
    # 1. Setup Input/Output Paths
    # We read from the QA 'quality' folder (Passed data)
    qa_dir = os.path.join(settings.data_dir, settings.qa_dir, settings.quality_data_dir)
    
    # Output dir for formatted datasets
    output_dir = os.path.join(settings.data_dir, settings.train_data_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📂 Reading from: {qa_dir}")
    print(f"📂 Saving to:   {output_dir}")
    
    # 2. Process SFT
    sft_files = sorted(glob.glob(os.path.join(qa_dir, "sft_*.jsonl")))
    if sft_files:
        ds_sft = process_sft_data(sft_files)
        save_path = os.path.join(output_dir, "sft_dataset.parquet")
        ds_sft.to_parquet(save_path)
        print(f"✅ SFT Dataset saved: {save_path} ({len(ds_sft)} rows)")
        
        # (Optional) Save a small sample JSON for visual inspection
        with open(os.path.join(output_dir, "sft_sample.json"), "w") as f:
            json.dump(ds_sft[0], f, indent=2, ensure_ascii=False)
    else:
        print("⚠️ No SFT files found.")

    # 3. Process DPO
    dpo_files = sorted(glob.glob(os.path.join(qa_dir, "dpo_*.jsonl")))
    if dpo_files:
        ds_dpo = process_dpo_data(dpo_files)
        save_path = os.path.join(output_dir, "dpo_dataset.parquet")
        ds_dpo.to_parquet(save_path)
        print(f"✅ DPO Dataset saved: {save_path} ({len(ds_dpo)} rows)")
        
        # (Optional) Save sample
        with open(os.path.join(output_dir, "dpo_sample.json"), "w") as f:
            json.dump(ds_dpo[0], f, indent=2, ensure_ascii=False)
    else:
        print("⚠️ No DPO files found.")

if __name__ == "__main__":
    main()