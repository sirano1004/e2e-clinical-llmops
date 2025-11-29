from . import soap, discharge

# 1. Central Registry
# This maps the 'task_type' string to the module
PROMPT_REGISTRY = {
    "soap": soap,
    "discharge": discharge,
}

DEFAULT_PROMPT = "You are a helpful medical assistant."

def get_system_prompt(task_type: str) -> str:
    """
    Retrieves the prompt for the given task.
    If the task module has a 'get_prompt' function, use it.
    Otherwise, fall back.
    """
    module = PROMPT_REGISTRY.get(task_type)
    
    if module and hasattr(module, "get_prompt"):
        return module.get_prompt()
    
    return DEFAULT_PROMPT