import os

from .runner import process_file
from ..config import settings

def main():
    os.makedirs(os.path.join(settings.data_dir, settings.parsed_data_dir), exist_ok=True)

    targets = [settings.sft_file, settings.dpo_file]
    
    for target in targets:
        process_file(target)

if __name__ == "__main__":
    main()