import os
from pathlib import Path
from typing import Optional, Dict, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Get the folder where THIS file (config.py) lives (i.e., 'backend/')
BASE_DIR = Path(__file__).resolve().parent
# Point exactly to the .env file in that folder
ENV_FILE_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    # ==========================================
    # 1. VLLM CONFIG
    # ==========================================
    vllm_model_name: str = Field(..., alias="TARGET_MODEL")
    vllm_temperature: float = 0.7
    vllm_tensor_parallel_size: int = 1 # GPU Counts
    vllm_max_model_len: int = 4096      # Max context length
    vllm_max_output_tokens: int = 1024  # Max output length
    vllm_enable_lora: bool = True       # Multi Lora enable
    vllm_gpu_utilization: float = Field(0.85, alias="GPU_UTILIZATION")
    vllm_enable_prefix_caching: bool = Field(True, alias="ENABLE_PREFIX_CACHING")
    vllm_stop_sequences_str: str = Field(..., alias="VLLM_STOP_SEQUENCES")
    vllm_max_num_seqs: int = Field(1, alias="MAX_NUM_SEQS")
    vllm_quantization: Optional[str] = None
    vllm_max_lora: int = Field(4, alias="MAX_LORA")

    # Convert str in to list
    @property
    def vllm_stop_sequences(self) -> List[str]:
        # deliminate using ','
        return [seq.strip() for seq in self.vllm_stop_sequences_str.split(',') if seq.strip()]
    # ==========================================
    # 2. MODEL IDENTITY
    # ==========================================
    target_model: str = Field(..., description="base model id from huggingface")
    lora_adapters: Optional[Dict[str, str]] = Field({}, description="lora adapters from huggingface")

    # ==========================================
    # 3. LORA HYPERPARAMETERS (Architecture)
    # ==========================================
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    
    # ==========================================
    # 4. AUDIO SETTINGS
    # ==========================================
    whisper_model_size: str = "small.en"

    # ==========================================
    # 5. SECRETS
    # ==========================================
    hf_token: str = Field(..., alias="HF_TOKEN")
    ngrok_auth_token: str = Field(..., alias="NGROK_AUTH_TOKEN")

    # ==========================================
    # 6. DATA PATHS
    # ==========================================
# 💡 Root directory for storing all data
    data_dir: str = Field("data_storage", alias="DATA_DIR")
    
    # 💡 Filenames for each data type
    raw_log_file: str = Field("system_logs.jsonl", alias="RAW_LOG_FILE")
    sft_file: str = Field("sft_train_data.jsonl", alias="SFT_FILE")
    dpo_file: str = Field("dpo_train_data.jsonl", alias="DPO_FILE")

    # ==========================================
    # 7. REDIS (Memory)
    # ==========================================
    redis_host: str = Field("localhost", alias="REDIS_HOST")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    redis_db: int = Field(0, alias="REDIS_DB")
    # ==========================================)

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