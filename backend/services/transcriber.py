import os
import torch
import whisperx
import gc
from typing import Dict, Any, List
import spacy
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
# --- Project Imports (Relative Paths) ---
from ..core.config import settings
from ..schemas import DialogueTurn
from ..core.logger import logger
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
        self.device = "cpu" #"cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "int8" #"int8" if self.device == "cuda" else "int8"
        self.batch_size = 2 # Adjust based on remaining VRAM
        
        logger.info(f"🎤 Initializing WhisperX on {self.device} ({self.compute_type})...")
        
        # 1. Load Whisper Model (ASR)
        try:
            self.model = whisperx.load_model(
                settings.whisper_model_size, 
                self.device, 
                compute_type=self.compute_type,
                language="en" # Force English for consistency in this MVP
            )

            logger.info("⏳ Loading Alignment Model (English)...")
            self.align_model, self.align_metadata = whisperx.load_align_model(
                language_code="en", 
                device=self.device
            )

            logger.info("✅ Whisper model loaded.")
        except Exception as e:
            logger.exception(f"❌ Failed to load Whisper model: {e}")
            raise

        # 2. Diarization Model Removed
        # We now rely on the LLM (Brain) to infer speakers from context later.
        self.diarize_model = None 
        logger.info("⏩ Skipping Diarization Model (handled by LLM).")
        
        logger.info("🧠 Loading Spacy for Smart Formatting...")
        try:
            # disable=['ner', 'parser']
            self.nlp = spacy.load("en_core_web_lg", disable=["ner", "parser"])
        except:
            self.nlp = None
    def transcribe_audio(self, audio_path: str, chunk_index: int, confidence_threshold: float = 0.6) -> Dict[str, Any]:
        """
        Executes the full pipeline: Transcribe -> Align -> Diarize -> Format.
        Returns a dictionary compatible with the TranscriptionResponse schema.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"🎧 Processing audio: {audio_path}")
        
        try:
            # --- Step 1: Transcribe (ASR) ---
            audio = whisperx.load_audio(audio_path)
            # VAD and batching make this significantly faster than standard Whisper
            result = self.model.transcribe(audio, batch_size=self.batch_size)
            
            # --- Step 2: Align (Word Timestamps) ---            
            # Perform forced alignment to get accurate word timings
            result = whisperx.align(
                result["segments"], 
                self.align_model, 
                self.align_metadata, 
                audio, 
                device=self.device, 
                return_char_alignments=False
            )
            
            # 💡 CRITICAL: Memory Cleanup
            # We must delete the alignment model immediately to free VRAM for vLLM.
            torch.cuda.empty_cache()

            # --- Step 3: Diarize (Speaker ID) - REMOVED ---
            # We skip the heavy diarization model.
            # Raw segments imply "Unknown Speaker" until LLM processes them.
            
            # --- Step 4: Format for Schema ---
            return self._format_response(result, confidence_threshold, chunk_index)

        except Exception as e:
            logger.exception(f"❌ Transcription Pipeline Failed: {e}")
            raise e
        finally:
            # Final garbage collection to ensure no tensors leak
            gc.collect()
            torch.cuda.empty_cache()

    def _format_response(self, result: Dict[str, Any], threshold: float, chunk_index: int) -> Dict[str, Any]:
        """
        Maps raw WhisperX output to our Pydantic schema structure.
        INCLUDES HEURISTIC MERGE: Combines segments if gap < 0.5s.
        """
        conversation_output = [] 
        raw_segments = []

        # --- 1. SMART MERGE LOGIC ---
        # We assume that if the silence is < 0.5s, it is the same speaker continuing their thought.
        merged_segments = []
        
        if result["segments"]:
            # Start with the first segment
            current_seg = result["segments"][0]
            
            for next_seg in result["segments"][1:]:
                # Calculate silence gap
                gap = next_seg["start"] - current_seg["end"]
                
                if gap < 0.5:
                    # MERGE THEM!
                    # 1. Combine Text
                    current_seg["text"] += " " + next_seg["text"]
                    
                    # 2. Extend End Time
                    current_seg["end"] = next_seg["end"]
                    
                    # 3. Combine 'words' list (Crucial for Red Underlines)
                    if "words" in current_seg and "words" in next_seg:
                        current_seg["words"].extend(next_seg["words"])
                        
                else:
                    # Gap is too big -> This is likely a new turn or new speaker.
                    merged_segments.append(current_seg)
                    current_seg = next_seg
            
            # Don't forget the last segment
            merged_segments.append(current_seg)

        # --- 2. FORMATTING LOOP (Uses merged_segments now) ---
        CRITICAL_POS_TAGS = ["NUM", "PROPN", "NOUN", "ADJ"]
        IGNORE_WORDS = {
            "i", "you", "he", "she", "it", "we", "they", "my", "your", "his", "her", "its", "our", "their",
            "and", "but", "or", "so", "because", "if", "then", "with", "at", "on", "in", "to", "for", "of",
            "yeah", "yep", "yes", "no", "nah", "okay", "ok", "right", "sure",
            "um", "uh", "ah", "hmm", "oh", "like", "well", "just"
        }

        for segment in merged_segments:
            # Default placeholder. The LLM will assign "Doctor" or "Patient" later.
            speaker = "TBD"
            segment_text = segment.get("text", "")

            # NLP Analysis for context-aware POS tagging
            doc = self.nlp(segment_text) if self.nlp else None
            spacy_tokens = [token for token in doc] if doc else []

            segment_ui_words = []
            segment_llm_words = []

            # WhisperX segments contain a 'words' list
            if "words" in segment:
                for i, w in enumerate(segment["words"]):
                    word_text = w.get("word", "")
                    conf = round(w.get("score", 0.0), 2)
                    clean_word = word_text.strip()
                    clean_word_lower = clean_word.lower().replace(".", "").replace(",", "").replace("?", "").replace("!", "")

                    # --- 🧠 Smart Logic (Calculate ONCE) ---
                    is_significant = False
                    
                    # 🚨 Check 1: Is it in the Ignore List? (Priority 1)
                    if clean_word_lower in IGNORE_WORDS:
                        is_significant = False
                        
                    # Check 2: Spacy Analysis (Priority 2)
                    elif doc and i < len(spacy_tokens):
                        token = spacy_tokens[i]
                        if token.pos_ in CRITICAL_POS_TAGS and not token.is_stop:
                            is_significant = True
                    else:
                        # Fallback heuristic: length > 3 implies potential significance
                        if len(clean_word) > 3:
                            is_significant = True
                    
                    # Final Decision: Mark as unclear ONLY if low confidence AND significant
                    should_flag = (conf < threshold) and is_significant

                    # --- A. Collect Data for UI (Boolean Flag) ---
                    segment_ui_words.append({
                        "word": word_text,
                        "start": w.get("start", 0.0),
                        "end": w.get("end", 0.0),
                        "is_unclear": should_flag # 💡 Simply True/False
                    })

                    # --- B. Format Text for LLM ---
                    if should_flag:
                        segment_llm_words.append(f"(unclear: {clean_word})")
                    else:
                        segment_llm_words.append(clean_word)
            
                # Rebuild the full text string
                formatted_sentence = " ".join(segment_llm_words)

            else:
                # Fallback if alignment failed
                formatted_sentence = segment["text"]

            # --- 3. BUILD OUTPUT OBJECTS ---
            
            # A. The object for the LLM (History)
            conversation_output.append(DialogueTurn(
                role=speaker,
                content=formatted_sentence,
                chunk_index=chunk_index
            ))
            
            # B. The object for the Frontend UI (Highlights)
            raw_segments.append({
                "start": segment.get("start", 0.0),
                "end": segment.get("end", 0.0),
                "speaker": speaker,
                "words": segment_ui_words
            })

        return {
            "conversation": conversation_output, 
            "raw_segments": raw_segments
        }

# Singleton Instance
# Models are loaded upon import (be mindful of startup time)
transcriber_service = TranscriberService()