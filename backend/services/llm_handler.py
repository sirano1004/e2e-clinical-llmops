import time
import json
from typing import Dict, Any, Optional, List, Union

# --- VLLM Core Imports ---
from vllm.engine.async_llm_engine import AsyncLLMEngine
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.sampling_params import SamplingParams, GuidedDecodingParams
from vllm.lora.request import LoRARequest

# --- HF Tokenizer Import ---
from transformers import AutoTokenizer

# --- Project Imports (Robust Relative Paths) ---
# Import settings from the parent backend package
from ..core.config import settings
# Import Pydantic models for data validation
from ..schemas import (
    ScribeRequest, 
    ScribeResponse, 
    SOAPNote,
    SOAPItem,
    SOAPNoteGeneration
) 
# Import Custom Logger
from ..core.logger import logger
# Import prompt for each task
from ..prompts import get_system_prompt, get_suffix_prompt
# Import Redis session service
from ..repositories.metrics import metrics_service

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
        )
        
        # 2. Initialize the AsyncLLMEngine
        # This step downloads the model (if needed) and allocates GPU memory.
        # WARNING: This takes 3-5 minutes and blocks the process during startup.
        logger.info(f"🔄 Initializing AsyncLLMEngine for model: {settings.vllm_model_name}...")
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)
        logger.info("✅ AsyncLLMEngine initialized successfully.")

        # 3. Create LoRA Integer ID Map
        # VLLM requires a unique integer ID for each adapter.
        # We pre-calculate this to prevent hash collisions at runtime.
        # IDs start at 1 because 0 is often reserved or used for the base model.
        self.lora_id_map = {
            name: index + 1 
            for index, name in enumerate(settings.lora_adapters.keys())
        }
        logger.info(f"✅ LoRA ID Map created: {self.lora_id_map}")

        # 4. Load Tokenizer to apply chat template
        logger.info(f"Loading tokenizer for: {settings.vllm_model_name}")
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
                             lora_request_object: Optional[LoRARequest] = None,
                             guided_decoding: Optional[GuidedDecodingParams] = None) -> str:
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
            guided_decoding=guided_decoding
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
            logger.exception(f"❌ VLLM Execution Error for request {request_id}: {e}")
            raise RuntimeError(f"LLM inference failed: {e}") from e

    # ====================================================================
    # HIGH-LEVEL ORCHESTRATION (Task Specific)
    # ====================================================================

    async def generate_scribe(self, request: ScribeRequest) -> ScribeResponse:
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
        adapter_key = "soap" if "soap" in request.task_type else request.task_type        
        lora_path = settings.lora_adapters.get(adapter_key)

        # Check if LoRA is enabled, mapped, and path exists
        if settings.vllm_enable_lora and lora_path and adapter_key in self.lora_id_map:
            
            if lora_path:
                lora_request_object = LoRARequest(
                    lora_name=adapter_key,                 
                    lora_int_id=self.lora_id_map.get(adapter_key), # Use pre-calculated unique ID
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
        
        # 3. Context Serialization
        # Convert the SOAPNote object to a JSON string for the LLM to read.
        if request.existing_notes:
            # Ensure we serialize it to a formatted JSON string
            context_str = request.existing_notes.model_dump_json(indent=2)
        else:
            context_str = "None"

        # 4. Suffix Strategy (Task-Specific Instructions)
        # The instruction is appended at the very end.
        suffix_prompt = get_suffix_prompt(request.task_type, context_str)

        # Append the specific instruction as the last user message
        messages.append({"role": "user", "content": suffix_prompt})

        # 5. Execution
        # full_prompt passed from app.py already contains the Dialogue History
        raw_response = await self._execute_prompt(
            messages=messages,
            temperature=request.temperature,
            lora_request_object=lora_request_object,
            guided_decoding=GuidedDecodingParams(json=SOAPNoteGeneration.model_json_schema())
        )
        
        duration = (time.time() - start_time) * 1000

        await metrics_service.update_metrics(request.session_id, duration, 'total_latency_ms')
        
        # Calculate current chunk index (Source ID)
        # Assuming the new info comes from the latest chunk added
        current_chunk_idx = request.chunk_index
        
        # 6. Validation & Formatting
        # Parse the raw text into structured data (SOAPNote or Dict)
        parsed_summary = self._parse_output(raw_response, adapter_key, current_chunk_idx)

        return ScribeResponse(
            session_id=request.session_id,
            interaction_id=f"gen-{time.time()}", 
            generated_summary=parsed_summary,
            chunk_index=current_chunk_idx
        )

    # ====================================================================
    # HELPER METHODS
    # ====================================================================

    def _parse_output(self, raw_text: str, task_type: str, chunk_idx: int = 0) -> Union[SOAPNote, Dict[str, Any], str]:
        """
        Parses LLM output. If task is SOAP, attempts to extract and validate JSON.
        Returns raw text if parsing fails to prevent app crash.
        """
        if task_type in ["soap"]:
            try:
                # Regex to find the first JSON object in the output (ignoring Markdown)
                clean_text = raw_text.strip()
                if "```" in clean_text:
                    clean_text = clean_text.split("```")[1]
                    if clean_text.startswith("json"):
                        clean_text = clean_text[4:] # remove 'json'
                
                # Load JSON
                data = json.loads(clean_text)
                
                # Convert raw strings to SOAPItems with ID & Source
                structured_data = {}
                for key in ["subjective", "objective", "assessment", "plan"]:
                    raw_list = data.get(key, [])
                    item_list = []
                    for text_content in raw_list:
                        if isinstance(text_content, str):
                            # Create Trackable Item
                            item_list.append(SOAPItem(
                                text=text_content,
                                source_chunk_index=chunk_idx
                            ))
                    structured_data[key] = item_list
                
                return SOAPNote(**structured_data)
            
            except (json.JSONDecodeError, Exception) as e:
                logger.exception(f"⚠️ JSON Parsing Failed: {e}")
                # Fallback: Wrap raw text in a dict structure so Frontend can display it
                return SOAPNote()
        
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