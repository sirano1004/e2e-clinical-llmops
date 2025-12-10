from transformers import pipeline
from sentence_transformers import CrossEncoder
from functools import lru_cache
from .logger import logger

@lru_cache(maxsize=1)
def get_ner_pipeline():
    print("🔄 Loading NER Model... (This should happen only ONCE)")
    return pipeline(
                "token-classification", 
                model="d4data/biomedical-ner-all", 
                aggregation_strategy="first", 
                device=-1 # Run on CPU to save GPU VRAM for vLLM
            )

@lru_cache(maxsize=1)
def get_nli_pipeline():
    logger.info(f"🛡️ Loading Medical NLI Model...")
    return CrossEncoder("cross-encoder/nli-deberta-v3-base", device='cpu')
    
