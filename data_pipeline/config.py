from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Get the folder where THIS file (config.py) lives (i.e., 'backend/')
BASE_DIR = Path(__file__).resolve().parent.parent
# Point exactly to the .env file in that folder
ENV_FILE_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    # Code version
    data_pipeline_version: str = "v1.0.0"

    # 💡 Root directory for storing all data
    data_dir: str = Field("data_storage", alias="DATA_DIR")
    
    # 💡 Folders for each steps
    raw_data_dir: str = Field("logs", alias="RAW_DATA_DIR")
    parsed_data_dir: str = Field("parsed", alias="PARSED_DATA_DIR")
    curated_data_dir: str = Field("curated", alias="CURATED_DATA_DIR")
    ready_data_dir: str = Field("ready", alias="READY_DATA_DIR")

    # 💡 Filenames for each data type
    sft_file: str = Field("sft_train_data.jsonl", alias="SFT_FILE")
    dpo_file: str = Field("dpo_train_data.jsonl", alias="DPO_FILE")

    # Load from .env file
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_ignore_empty=True,
        extra="ignore"
    )

# Initialize
settings = Settings()
print(f"✅ Configuration Loaded")
print(settings)