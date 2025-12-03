import json
import asyncio
import re
from typing import List, Set, Union, Dict, Any

# --- Hugging Face Libraries ---
from transformers import pipeline
from sentence_transformers import CrossEncoder

# --- Project Imports ---
from ..schemas import DialogueTurn
from ..core.logger import logger

class GuardrailService:
    """
    Quality Assurance Service (Hugging Face All-In-One Edition).
    
    Strategy:
    1. Medical NER: Uses 'd4data/biomedical-ner-all' (BERT-based) via HF Pipeline.
    2. NLI Check: 'cross-encoder/nli-deberta-v3-base' (General SOTA)
    * Why General? It detects logical contradictions (negation) better 
    than embeddings, and open-source medical cross-encoders are rare.
    """

    def __init__(self):
        logger.info("🛡️ Initializing Guardrail Services (HF Models)...")
        
        # 1. Load Medical NER Pipeline (Hugging Face)
        # We use 'd4data/biomedical-ner-all' which detects Medications, Diseases, Symptoms, etc.
        # aggregation_strategy="simple" merges tokens like "di" "##abe" "##tes" into "diabetes".
        try:
            logger.info("🛡️ Loading HF NER Pipeline (d4data/biomedical-ner-all)...")
            self.ner_pipeline = pipeline(
                "token-classification", 
                model="d4data/biomedical-ner-all", 
                aggregation_strategy="first",
                device=-1 # Run on CPU (-1) to save GPU for vLLM
            )
            logger.info("✅ Medical NER pipeline loaded.")
        except Exception as e:
            logger.exception(f"❌ Failed to load NER pipeline: {e}")
            self.ner_pipeline = None

        # 2. Load Medical NLI Model (Cross-Encoder)
        try:
            model_id = "cross-encoder/nli-deberta-v3-base"
            logger.info(f"🛡️ Loading Medical NLI Model ({model_id})...")
            self.nli_model = CrossEncoder(model_id, device='cpu')
            
            # MedNLI Label Mapping: 0: Contradiction, 1: Entailment, 2: Neutral
            self.label_map = {0: "contradiction", 1: "entailment", 2: "neutral"}
            logger.info("✅ Medical NLI model loaded.")
        except Exception as e:
            logger.exception(f"❌ Failed to load NLI model: {e}")
            self.nli_model = None

    async def check_hallucination(self, transcript: List[DialogueTurn], summary: Union[str, dict]) -> List[str]:
        """
        Public Method: Non-blocking wrapper.
        Offloads heavy calculation to a separate thread.
        """
        # 1. Data Prep (Flattening)
        transcript_text = "\n".join([f"{t.role}: {t.content}" for t in transcript])
        summary_text = self._clean_summary(summary)

        # 2. Run in Executor (Non-blocking)
        loop = asyncio.get_running_loop()
        
        try:
            logger.info("🛡️ Starting Guardrail Analysis (Threaded)...")
            
            # Use 'None' to use the default ThreadPoolExecutor
            analysis_result = await loop.run_in_executor(
                None, 
                self._run_analysis_sync,
                transcript_text,
                summary_text
            )
            
            # Log summary of results
            w_count = len(analysis_result["warnings"])
            if w_count > 0:
                logger.warning(f"⚠️ Guardrail issues: {w_count}. Metrics: {analysis_result['metrics']}")
            else:
                logger.info(f"✅ Guardrail passed. Metrics: {analysis_result['metrics']}")

            return analysis_result

        except Exception as e:
            logger.exception(f"❌ Guardrail execution failed: {e}")
            # Fail-safe: Return empty structure on error
            return {"warnings": [], "metrics": {}}

    def _clean_summary(self, partial_summary: Union[Dict, str]) -> str:
        """
        Converts partial JSON output into clean text for NER.
        Removes metadata tags like '(Updated)' to avoid NER confusion.
        """
        if isinstance(partial_summary, str):
            return partial_summary
            
        text_parts = []
        # Iterate over known SOAP keys to extract text lists
        for key, items in partial_summary.items():
            if isinstance(items, list):
                for item in items:
                    # Remove tags: "Headache (Updated)" -> "Headache"
                    clean_item = re.sub(r"\s*\((Updated|Correction)\)", "", item, flags=re.IGNORECASE)
                    text_parts.append(clean_item)
            elif isinstance(items, str):
                text_parts.append(items)
                
        return ". ".join(text_parts)

    def _check_medical_ner(self, transcript: str, summary: str) -> Dict[str, Any]:
        """
        Extracts medical entities using Hugging Face Pipeline.
        """
        # Initialize structure
        output = {
            "warnings": [],
            "metrics": {
                "transcript_count": 0,    # Recall Denominator
                "summary_count": 0,       # Precision Denominator
                "matched_count": 0,       # Numerator (Intersection)
                "hallucination_count": 0  # Error Count
            }
        }

        if not transcript or not summary:
            return output        
        # Extract entities using HF pipeline
        # Returns list of dicts: [{'entity_group': 'Disease_disorder', 'word': 'diabetes', ...}]
        trans_results = self.ner_pipeline(transcript)
        summ_results = self.ner_pipeline(summary)

        def get_medical_entities(results: List[Dict]) -> Set[str]:
            entities = set()
            # Valid labels in 'd4data/biomedical-ner-all' relevant to hallucination:
            target_labels = [
                "Disease_disorder",       
                "Medication",             
                "Sign_symptom",           
                "Diagnostic_procedure",   
                "Biological_structure",   
                "Severity",               
                "Date",                   
                "Duration",               
                "Frequency",              
                "Dosage",                 
                # "Administration_route"  
            ]
            
            for item in results:
                label = item.get('entity_group')
                word = item.get('word').strip().lower()
                
                if label in target_labels and len(word) > 2: # Ignore noise
                    entities.add(word)
            return entities

        trans_ents = get_medical_entities(trans_results)
        summ_ents = get_medical_entities(summ_results)

        # 3. Calculate Logic (Set Operations)
        matched_ents = summ_ents.intersection(trans_ents)
        unsupported_ents = summ_ents - trans_ents

        # 4. Fill Warnings
        for h in unsupported_ents:
            output["warnings"].append(f"Unverified entity: '{h}'")

        # Identify entities in Summary NOT in Transcript
        unsupported_ents = summ_ents - trans_ents
        
        # 5. Fill Metrics
        output["metrics"]["transcript_count"] = len(trans_ents)
        output["metrics"]["summary_count"] = len(summ_ents)
        output["metrics"]["matched_count"] = len(matched_ents)
        output["metrics"]["hallucination_count"] = len(unsupported_ents)

        return output

    def _check_medical_nli(self, transcript: str, summary: str) -> List[str]:
        """
        Uses MedNLI DeBERTa to check logical consistency.
        """
        warnings = []
        
        # Simple sentence splitting (since we removed Spacy, we use simple split)
        # For production, consider using 'nltk.sent_tokenize' or just split by '. '
        summary_sentences = [s.strip() for s in summary.split('.') if len(s.strip()) > 10]

        # Construct Pairs: (Transcript, Summary Sentence)
        pairs = [(transcript, sent) for sent in summary_sentences]
        
        if not pairs:
            return []

        # Predict
        scores = self.nli_model.predict(pairs)
        
        for i, score_array in enumerate(scores):
            label_idx = score_array.argmax()
            label = self.label_map[label_idx]
            sentence = pairs[i][1]
            
            if label == "contradiction": 
                warnings.append(f"Medical Contradiction: '{sentence}' contradicts the transcript.")
            elif label == "neutral":
                 warnings.append(f"Unverified Fact: '{sentence}' is not explicitly supported.")

        return warnings

    def _run_analysis_sync(self, transcript: str, summary: str) -> Dict[str, Any]:
        """
        Synchronous wrapper. Aggregates results from NER and NLI.
        This function will be run in a separate thread.
        """
        final_result = {
            "warnings": [],
            "metrics": {
                # Defaults
                "transcript_count": 0,    
                "summary_count": 0,   
                "matched_count": 0,  
                "hallucination_count": 0    
            }
        }

        # 1. NER Check (Returns dict with warnings & metrics)
        if self.ner_pipeline:
            ner_output = self._check_medical_ner(transcript, summary)
            
            # Merge results explicitly
            final_result["warnings"].extend(ner_output["warnings"])
            final_result["metrics"].update(ner_output["metrics"])

        # 2. NLI Check (Optional / Logical Consistency)
        # Only run if there is summary text to check
        if self.nli_model and summary.strip():
            # Pass the list to append contradictions
            nli_warnings = self._check_medical_nli(transcript, summary)
            final_result["warnings"].extend(nli_warnings)

        return final_result

guardrail_service = GuardrailService()