import json
import os
import aiofiles
from datetime import datetime
from typing import Dict, Any, List

# --- Project Imports ---
from ..core.config import settings
from ..core.logger import logger

class LocalStorageClient:
    """
    Manages local file storage (JSONL) for data collection (SFT/DPO).
    Mimics a database connection but writes to local files for simplicity.
    """

    def __init__(self):
        # Ensure the storage directory exists based on config
        self.data_dir = settings.data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info(f"📁 Created data directory: {self.data_dir}")

    async def append_record(self, filename: str, record: Dict[str, Any]):
        """
        Appends a single dictionary record to a JSONL file asynchronously.
        
        Args:
            filename: The name of the file (e.g., "sft_train.jsonl").
            record: The data dictionary to save.
        """
        file_path = os.path.join(self.data_dir, filename)
        
        # Add metadata (Timestamp) for audit purposes
        # using .copy() to avoid modifying the original dict reference
        save_data = record.copy()
        save_data["_created_at"] = datetime.now().astimezone().isoformat()
        
        try:
            # Open in 'append' mode asynchronously
            # ensure_ascii=False ensures non-English characters (Korean) are saved correctly
            async with aiofiles.open(file_path, mode='a', encoding='utf-8') as f:
                json_line = json.dumps(save_data, ensure_ascii=False)
                await f.write(json_line + "\n")
                
        except Exception as e:
            logger.error(f"❌ Failed to write to {filename}: {e}")
            raise e

    async def get_all_records(self, filename: str) -> List[Dict[str, Any]]:
        """
        Reads all records from a JSONL file.
        Useful for analytics, debugging, or creating a download export.
        """
        file_path = os.path.join(self.data_dir, filename)
        if not os.path.exists(file_path):
            return []

        records = []
        try:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                async for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        except Exception as e:
            logger.error(f"❌ Failed to read {filename}: {e}")
            return []
            
        return records

# Singleton Instance
local_storage = LocalStorageClient()