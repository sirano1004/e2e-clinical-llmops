import os
import torch
import whisperx
import gc
from typing import Dict, Any, List

# --- Project Imports (Relative Paths) ---
from ..config import settings
from ..schemas import DialogueTurn

class TranscriberService:
    """
    Manages the WhisperX pipeline for State-of-the-Art Speech-to-Text.
    
    Pipeline Steps:
    1. VAD (Voice Activity Detection) to filter silence.
    2. Batch Processing for high throughput ASR.
    3. Forced Alignment for precise word-level timestamps.
    4. Speaker Diarization using PyAnnote (via WhisperX).
    """

    def __init__(self):
        # Detect hardware. WhisperX requires CUDA for alignment/diarization usually.
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.batch_size = 2 # Adjust based on remaining VRAM
        
        print(f"🎤 Initializing WhisperX on {self.device} ({self.compute_type})...")
        
        # 1. Load Whisper Model (ASR)
        # 'large-v2' offers the best trade-off for medical terminology accuracy.
        try:
            self.model = whisperx.load_model(
                "large-v2", 
                self.device, 
                compute_type=self.compute_type,
                language="en" # Force English for consistency in this MVP
            )
            print("✅ Whisper model loaded.")
        except Exception as e:
            print(f"❌ Failed to load Whisper model: {e}")
            raise

        # 2. Load Diarization Model (PyAnnote)
        # This requires a valid HF_TOKEN in .env with access to 'pyannote/speaker-diarization-3.1'
        try:
            self.diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=settings.hf_token,
                device=self.device
            )
            print("✅ Diarization pipeline loaded.")
        except Exception as e:
            print(f"⚠️ Warning: Diarization model failed to load. Check HF_TOKEN permissions. Error: {e}")
            self.diarize_model = None

    def transcribe_audio(self, audio_path: str, confidence_threshold: float = 0.6) -> Dict[str, Any]:
        """
        Executes the full pipeline: Transcribe -> Align -> Diarize -> Format.
        Returns a dictionary compatible with the TranscriptionResponse schema.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        print(f"🎧 Processing audio: {audio_path}")
        
        try:
            # --- Step 1: Transcribe (ASR) ---
            audio = whisperx.load_audio(audio_path)
            # VAD and batching make this significantly faster than standard Whisper
            result = self.model.transcribe(audio, batch_size=self.batch_size)
            
            # --- Step 2: Align (Word Timestamps) ---
            # We load the alignment model specifically for the detected language.
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"], 
                device=self.device
            )
            
            # Perform forced alignment to get accurate word timings
            result = whisperx.align(
                result["segments"], 
                model_a, 
                metadata, 
                audio, 
                device=self.device, 
                return_char_alignments=False
            )
            
            # 💡 CRITICAL: Memory Cleanup
            # We must delete the alignment model immediately to free VRAM for vLLM.
            del model_a
            torch.cuda.empty_cache()

            # --- Step 3: Diarize (Speaker ID) ---
            if self.diarize_model:
                diarize_segments = self.diarize_model(audio)
                # Assign speaker labels to the aligned word segments
                result = whisperx.assign_word_speakers(diarize_segments, result)

            # --- Step 4: Format for Schema ---
            return self._format_response(result, confidence_threshold)

        except Exception as e:
            print(f"❌ Transcription Pipeline Failed: {e}")
            raise e
        finally:
            # Final garbage collection to ensure no tensors leak
            gc.collect()
            torch.cuda.empty_cache()

    def _format_response(self, result: Dict[str, Any], threshold: float) -> Dict[str, Any]:
        """
        Maps raw WhisperX output to our Pydantic schema structure.
        - Converts raw text into List[DialogueTurn]
        - Tags low-confidence words with (unclear: ...)
        """
        conversation_output = [] 
        raw_segments = []
        
        for segment in result["segments"]:
            # Default to "UNKNOWN" if diarization failed or wasn't run
            speaker = segment.get("speaker", "UNKNOWN")
            
            segment_ui_words = []
            segment_llm_words = []
            
            # WhisperX segments contain a 'words' list
            if "words" in segment:
                for w in segment["words"]:
                    # 1. Extract Word Data
                    word_text = w.get("word", "")
                    # WhisperX uses 'score' (0-1), mapping to confidence
                    conf = round(w.get("score", 0.0), 2)
                    start = w.get("start", 0.0)
                    end = w.get("end", 0.0)

                    # 2. Collect Data for UI (Red Underlines)
                    segment_ui_words.append({
                        "word": word_text,
                        "start": start,
                        "end": end,
                        "confidence": conf
                    })

                    # 3. Format Text for LLM (Apply Uncertainty Tag)
                    clean_word = word_text.strip()
                    if conf < threshold:
                        # This tag helps the LLM recognize uncertain inputs
                        segment_llm_words.append(f"(unclear: {clean_word})")
                    else:
                        segment_llm_words.append(clean_word)
            
            # Reconstruct the sentence with tags applied
            formatted_sentence = " ".join(segment_llm_words)
            
            # 💡 Create Structured Dialogue Object
            # This allows app.py to easily swap 'SPEAKER_01' with 'Doctor' later
            conversation_output.append(DialogueTurn(
                role=speaker,
                content=formatted_sentence
            ))
            
            # Create UI Metadata Object
            raw_segments.append({
                "id": 0, # Placeholder ID
                "start": segment.get("start", 0.0),
                "end": segment.get("end", 0.0),
                "text": formatted_sentence,
                "speaker": speaker, # Ensure speaker is passed to UI
                "avg_confidence": 0.0, # Placeholder, implies average of words
                "words": segment_ui_words
            })

        return {
            "conversation": conversation_output, 
            "raw_segments": raw_segments
        }

# Singleton Instance
# Models are loaded upon import (be mindful of startup time)
transcriber_service = TranscriberService()