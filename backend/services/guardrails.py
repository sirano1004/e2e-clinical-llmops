import json
from typing import List, Set, Union, Dict

# --- Hugging Face Libraries ---
from transformers import pipeline
from sentence_transformers import CrossEncoder

# --- Project Imports ---
from ..schemas import DialogueTurn

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
        print("🛡️ Initializing Guardrail Services (HF Models)...")
        
        # 1. Load Medical NER Pipeline (Hugging Face)
        # We use 'd4data/biomedical-ner-all' which detects Medications, Diseases, Symptoms, etc.
        # aggregation_strategy="simple" merges tokens like "di" "##abe" "##tes" into "diabetes".
        try:
            print("🛡️ Loading HF NER Pipeline (d4data/biomedical-ner-all)...")
            self.ner_pipeline = pipeline(
                "token-classification", 
                model="d4data/biomedical-ner-all", 
                aggregation_strategy="first",
                device=-1 # Run on CPU (-1) to save GPU for vLLM
            )
            print("✅ Medical NER pipeline loaded.")
        except Exception as e:
            print(f"❌ Failed to load NER pipeline: {e}")
            self.ner_pipeline = None

        # 2. Load Medical NLI Model (Cross-Encoder)
        try:
            model_id = "cross-encoder/nli-deberta-v3-base"
            print(f"🛡️ Loading Medical NLI Model ({model_id})...")
            self.nli_model = CrossEncoder(model_id, device='cpu')
            
            # MedNLI Label Mapping: 0: Contradiction, 1: Entailment, 2: Neutral
            self.label_map = {0: "contradiction", 1: "entailment", 2: "neutral"}
            print("✅ Medical NLI model loaded.")
        except Exception as e:
            print(f"❌ Failed to load NLI model: {e}")
            self.nli_model = None

    async def check_hallucination(self, transcript: List[DialogueTurn], summary: Union[str, dict]) -> List[str]:
        """
        Orchestrates the Hallucination Check pipeline.
        """
        warnings = []
        
        # 1. Prepare Data
        transcript_text = "\n".join([f"{t.role}: {t.content}" for t in transcript])
        
        if isinstance(summary, dict):
            # Extract clinical text fields only
            summary_parts = [
                str(summary.get("subjective", "")),
                str(summary.get("objective", "")),
                str(summary.get("assessment", "")),
                str(summary.get("plan", ""))
            ]
            summary_text = ". ".join([p for p in summary_parts if p])
        else:
            summary_text = str(summary)

        # 2. Phase A: Medical NER Cross-Check (Fail Fast)
        if self.ner_pipeline:
            ner_warnings = self._check_medical_ner(transcript_text, summary_text)
            warnings.extend(ner_warnings)

        # 3. Phase B: Medical NLI Check (Deep Logic)
        if self.nli_model:
            nli_warnings = self._check_medical_nli(transcript_text, summary_text)
            warnings.extend(nli_warnings)
        
        return warnings

    def _check_medical_ner(self, transcript: str, summary: str) -> List[str]:
        """
        Extracts medical entities using Hugging Face Pipeline.
        """
        warnings = []
        
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

        # Identify entities in Summary NOT in Transcript
        unsupported_ents = summ_ents - trans_ents
        
        for ent in unsupported_ents:
            warnings.append(f"Entity Hallucination: Medical term '{ent}' found in summary but not in transcript.")

        return warnings

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

    def check_safety(self, summary: str) -> List[str]:
        return []

guardrail_service = GuardrailService()