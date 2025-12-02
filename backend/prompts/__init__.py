# backend/prompts/__init__.py
from . import soap, referral, scribe_system, role_service, certificate

# 1. System Prompt Router
SYSTEM_REGISTRY = {
    "role_service": role_service, 
    "soap": scribe_system,
    "soap_final": scribe_system,
    "referral": scribe_system,     # Referral also uses the generic Scribe identity
    "certificate": scribe_system   # Certificate also uses the generic Scribe identity
}

# 2. Suffix Registry
SUFFIX_REGISTRY = {
    "soap": soap,
    "soap_final": soap,
    "referral": referral,
    "certificate": certificate
}

def get_system_prompt(task_type: str) -> str:
    module = SYSTEM_REGISTRY.get(task_type)
    if hasattr(module, "get_prompt"):
        return module.get_prompt()
    return "You are a helpful medical assistant."

def get_suffix_prompt(task_type: str, context: str = "None") -> str:
    module = SUFFIX_REGISTRY.get(task_type)
    if module and hasattr(module, "get_suffix"):
        return module.get_suffix(task_type, context)
    return ""