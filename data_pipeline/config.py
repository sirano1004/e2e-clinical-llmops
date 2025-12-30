from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Code version
    data_pipeline_version: str = "v1.0.0"

    # 💡 Root directory for storing all data
    data_dir: str = Field("data_storage", alias="DATA_DIR")
    
    # 💡 Folders for each steps
    raw_data_dir: str = Field("logs", alias="RAW_DATA_DIR")
    parsed_data_dir: str = Field("parsed", alias="PARSED_DATA_DIR")
    dedup_data_dir: str = Field("dedup", alias = "DEDUP_DATA_DIR")
    hard_dedup_dir: str = Field("hard", alias = "HARD_DEDUP_DATA_DIR")
    soft_dedup_dir: str = Field("soft", alias = "SOFT_DEDUP_DATA_DIR")
    qa_dir: str = Field("qa", alias="QA_DATA_DIR")
    quality_data_dir: str = Field("pass", alias="QUALITY_DATA_DIR")
    quarantine_data_dir: str = Field("quarantine", alias="QUARANTINE_DATA_DIR")
    train_data_dir: str = Field("train", alias="TRAIN_DATA_DIR")

    # 💡 Filenames for each data type
    sft_file: str = Field("sft_train_data.jsonl", alias="SFT_FILE")
    dpo_file: str = Field("dpo_train_data.jsonl", alias="DPO_FILE")

    # Length filter config
    min_length: int = 500
    min_ratio: float = 0.1
    max_ratio: float = 0.8

    # 💡 MinHash Configs
    dedup_text_key: str = "text"
    dedup_id_key: str = "id"
    dedup_date_key: str = "session_start"

    n_gram: int = 4
    num_buckets: int = 2
    hashes_per_bucket: int = 4

# Initialize
settings = Settings()
print(f"✅ Configuration Loaded")