import time
import json
import re
import asyncio
from typing import Dict, Any, Optional, List, Union

# --- VLLM Core Imports ---
from vllm.engine.async_llm_engine import AsyncLLMEngine
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.sampling_params import SamplingParams
from vllm.lora.request import LoRARequest

# --- HF Tokenizer Import ---
from transformers import AutoTokenizer

# --- Project Imports (Robust Relative Paths) ---
# Import settings from the parent backend package
from ..config import settings
# Import Pydantic models for data validation
from ..schemas import (
    ScribeRequest, 
    ScribeResponse, 
    SOAPNote
) 
# Import prompt for each task
from ..prompts import get_system_prompt


class LLMHandler:
    """
    The 'Brain' of the backend.
    Manages the AsyncLLMEngine instance directly within the FastAPI process.
    
    Responsibilities:
    1. Initialize vLLM Engine (Blocking operation on startup).
    2. Manage GPU resources via PagedAttention configuration.
    3. Route requests to specific LoRA adapters dynamically.
    4. Execute non-blocking inference using asyncio.
    """

    def __init__(self):
        # 1. Prepare Engine Arguments from Config
        # These settings determine how VLLM manages GPU memory and models.
        engine_args = AsyncEngineArgs(
            model=settings.vllm_model_name,
            tensor_parallel_size=settings.vllm_tensor_parallel_size,
            
            # --- GPU Resource Control ---
            # Limits VRAM usage for KV Cache (crucial for sharing GPU with Whisper/OS)
            gpu_memory_utilization=settings.vllm_gpu_utilization, 
            max_model_len=settings.vllm_max_model_len,
            max_num_seqs=settings.vllm_max_num_seqs, # Max concurrent sequences in the scheduler
            
            # --- Optimization Features ---
            quantization=settings.vllm_quantization, # e.g., 'awq' for 4-bit models
            enable_prefix_caching=settings.vllm_enable_prefix_caching, # Reuses KV cache for multi-turn chat
            
            # --- Multi-LoRA Configuration ---
            enable_lora=settings.vllm_enable_lora,
            max_loras=4, # Max number of active adapters in VRAM
            lora_modules=settings.lora_adapters, # Pass the Dict[name, path] map to engine
            
            # NOTE: If using TensorRT-LLM, we would add: backend="tensorrt" here.
        )
        
        # 2. Initialize the AsyncLLMEngine
        # This step downloads the model (if needed) and allocates GPU memory.
        # WARNING: This takes 3-5 minutes and blocks the process during startup.
        print(f"🔄 Initializing AsyncLLMEngine for model: {settings.vllm_model_name}...")
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)
        print("✅ AsyncLLMEngine initialized successfully.")

        # 3. Create LoRA Integer ID Map
        # VLLM requires a unique integer ID for each adapter.
        # We pre-calculate this to prevent hash collisions at runtime.
        # IDs start at 1 because 0 is often reserved or used for the base model.
        self.lora_id_map = {
            name: index + 1 
            for index, name in enumerate(settings.lora_adapters.keys())
        }
        print(f"✅ LoRA ID Map created: {self.lora_id_map}")

        # 4. Load Tokenizer to apply chat template
        print(f"Loading tokenizer for: {settings.vllm_model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            settings.vllm_model_name, 
            token=settings.hf_token
        )        

    # ====================================================================
    # CORE EXECUTION FUNCTION (Low-Level)
    # ====================================================================

    async def _execute_prompt(self, 
                             messages: List[Dict[str, str]],
                             temperature: float,
                             lora_request_object: Optional[LoRARequest] = None) -> str:
        """
        Executes a raw prompt against the VLLM engine asynchronously.
        This is a reusable core function that handles the AsyncGenerator stream.
        """
        request_id = f"exec-{time.time()}"
        
        # 1. Apply Chat Template (The Tokenizer does the magic here)
        # This converts the list [{'role': 'user', ...}] into the model-specific string format
        # e.g., <|start_header_id|>user<|end_header_id|> ...
        full_prompt = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True # Adds the "<|start_header_id|>assistant" tag at the end
        )

        # Configure Sampling Parameters (Generation Rules)
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=settings.vllm_max_output_tokens, # Cap output length (e.g., 2048)
            stop=settings.vllm_stop_sequences,          # Stop tokens (e.g., <|eot_id|>)
        )
        
        try:
            # Submit request to the engine's queue
            results_generator = self.engine.generate(
                full_prompt,
                sampling_params,
                request_id,
                lora_request=lora_request_object, # Pass specific adapter or None (Base Model)
            )

            # Consume the AsyncGenerator
            # Since this function is for non-streaming response, we collect full text.
            final_output = ""
            async for output in results_generator:
                if output.outputs:
                    final_output = output.outputs[0].text
            
            return final_output.strip()

        except Exception as e:
            print(f"❌ VLLM Execution Error for request {request_id}: {e}")
            raise RuntimeError(f"LLM inference failed: {e}") from e

    # ====================================================================
    # HIGH-LEVEL ORCHESTRATION (Task Specific)
    # ====================================================================

    async def generate_scribe(self, request: ScribeRequest, previous_summary: Optional[str]) -> ScribeResponse:
        """
        Orchestrates the Scribing task:
        1. Determines which LoRA adapter to use based on task_type.
        2. Constructs the LoRARequest object.
        3. Calls the core execution function.
        4. Parses and validates the output structure (JSON/SOAP).
        """
        start_time = time.time()
        
        # --- 1. Dynamic LoRA Routing ---
        lora_request_object = None
        # Look up the adapter name from the task map (e.g., "soap" -> "lora_path")
        lora_path = settings.lora_adapters.get(request.task_type)
        
        # Check if LoRA is enabled, mapped, and path exists
        if settings.vllm_enable_lora and lora_path and request.task_type in self.lora_id_map:
            
            if lora_path:
                lora_request_object = LoRARequest(
                    lora_name=request.task_type,                 
                    lora_int_id=self.lora_id_map.get(request.task_type), # Use pre-calculated unique ID
                    lora_local_path=lora_path              
                )
                # Logging routing decision for debugging
                # print(f"🧠 Routing request to LoRA adapter: {adapter_name}")

        # --- B. Message List Construction (Your Logic) ---
        messages = []
        
        # 1. System Prompt
        messages.append({
            "role": "system", 
            "content": get_system_prompt(request.task_type)
        })

        # 2. Dialogue History (S1, S2, S3...)
        # We append each turn as a separate user message (or alternating user/assistant if diarized)
        # Note: If diarized, we can format content as "Doctor: ..." inside a user role, 
        # or map them if the model supports specific roles. 
        # For simplicity/robustness, we append them as context.
        for turn in request.dialogue_history:
            # Format: "Doctor: content"
            formatted_content = f"{turn.role.upper()}: {turn.content}"
            messages.append({"role": "user", "content": formatted_content})

        # 3. Handling Iterative Updates
        if previous_summary:
            messages.append({
                        "role": "user", 
                        "content": f"Here is the existing clinical summary so far:\n{previous_summary}"
                    })
            
            messages.append({
                "role": "user", 
                "content": f"Based on the conversation and the summary above, generate a {request.task_type.upper()}."
            })

        else:
            # First time generation
            messages.append({
                "role": "user", 
                "content": f"Generate a {request.task_type.upper()} note based on the conversation."
            })

        # --- 3. Execution ---
        # full_prompt passed from app.py already contains the Dialogue History
        raw_response = await self._execute_prompt(
            messages=messages,
            temperature=request.temperature,
            lora_request_object=lora_request_object
        )
        
        duration = (time.time() - start_time) * 1000

        # --- 4. Validation & Formatting ---
        # Parse the raw text into structured data (SOAPNote or Dict)
        parsed_summary = self._parse_output(raw_response, request.task_type)

        return ScribeResponse(
            session_id=request.session_id,
            interaction_id=f"gen-{time.time()}", 
            generated_summary=parsed_summary,
            model_used=settings.vllm_model_name,
            adapter_used=lora_path,
            processing_time_ms=duration,
            # Placeholders for post-processing guards
            safety_warnings=[],
            hallucination_warnings=[]
        )

    # ====================================================================
    # HELPER METHODS
    # ====================================================================

    def _parse_output(self, raw_text: str, task_type: str) -> Union[SOAPNote, Dict[str, Any], str]:
        """
        Parses LLM output. If task is SOAP, attempts to extract and validate JSON.
        Returns raw text if parsing fails to prevent app crash.
        """
        if task_type == "soap":
            try:
                # Regex to find the first JSON object in the output (ignoring Markdown)
                json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                clean_json = json_match.group(0) if json_match else raw_text
                
                # Load JSON
                data = json.loads(clean_json)
                
                # Validate against Pydantic Schema (SOAPNote)
                return SOAPNote(**data)
            
            except (json.JSONDecodeError, Exception) as e:
                print(f"⚠️ JSON Parsing Failed: {e}")
                # Fallback: Wrap raw text in a dict structure so Frontend can display it
                return {
                    "subjective": "PARSING ERROR",
                    "objective": "Please check raw output.",
                    "assessment": "",
                    "plan": "",
                    "raw_output": raw_text # Pass raw text for manual correction
                }
        
        # For non-structured tasks, return string directly
        return raw_text

    async def get_engine_config(self) -> Dict[str, Any]:
        """
        Retrieves internal engine configuration for monitoring.
        Useful for checking total VRAM and model settings on startup.
        """
        try:
            config = await self.engine.get_model_config()
            return {
                "model": config.model,
                "max_model_len": config.max_model_len,
                "gpu_memory_utilization": settings.vllm_gpu_utilization,
                "quantization": settings.vllm_quantization,
                "lora_enabled": settings.vllm_enable_lora,
                "active_adapters": list(self.lora_id_map.keys())
            }
        except Exception as e:
            return {"error": str(e)}

# Singleton Instance
# This instantiation triggers the model load when app.py imports it.
llm_service = LLMHandler()