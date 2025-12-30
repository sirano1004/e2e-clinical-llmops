import re
import unicodedata

def normalize_text(text: str) -> str:
    """
    Conservative normalization for deduplication ONLY.
    English-only, designed for hard / soft dedup filters.
    """
    if not text:
        return ""

    # Unicode canonicalization (critical)
    text = unicodedata.normalize("NFKC", text)

    # Case normalization
    text = text.lower()

    # Remove punctuation (keep letters, numbers, spaces)
    text = re.sub(r"[^a-z0-9\s]", "", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text