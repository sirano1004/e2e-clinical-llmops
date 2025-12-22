import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple

from ..core.logger import logger
from ..core.load_models import get_ner_pipeline

class ClinicalSafetyService:
    """
    Clinical Safety Layer (NER + Knowledge Graph Implementation).
    
    Architecture:
    1. Extraction: Uses 'd4data/biomedical-ner-all' to detect 'Medication' and 'Dosage' entities.
    2. Linking: Associates a Medication with a Dosage based on physical proximity in text.
    3. Verification: Checks the extracted dosage against a hard-coded Knowledge Graph limits.
    """

    def __init__(self):
        logger.info("🛡️ Initializing Clinical Safety Layer (NER-based)...")
        
        # 1. Knowledge Graph (In-Memory MVP)
        # Defines safety limits for common medications.
        # Key: Normalized Drug Name (lowercase)
        # Value: Safety constraints (limit in mg)
        self.drug_knowledge_graph = {
            "panadol": {"limit": 4000, "unit": "mg"},
            "paracetamol": {"limit": 4000, "unit": "mg"},
            "ibuprofen": {"limit": 3200, "unit": "mg"},
            "amoxicillin": {"limit": 3000, "unit": "mg"},
            "metformin": {"limit": 2550, "unit": "mg"},
            "aspirin": {"limit": 4000, "unit": "mg"}
        }

        # 2. Load Medical NER Pipeline
        # We use a BERT-based model fine-tuned for biomedical entities.
        # 'aggregation_strategy="simple"' merges sub-tokens (e.g., "pan", "##adol") into one word.
        try:
            self.ner_pipeline = get_ner_pipeline()
            logger.info("✅ Safety NER pipeline loaded.")
        except Exception as e:
            logger.exception(f"❌ Failed to load Safety NER: {e}")
            self.ner_pipeline = None

    def _detect_rule_violations(self, summary_text: str) -> List[str]:
        """
        Main entry point. Scans text for safety violations.
        """
        if not self.ner_pipeline:
            return []

        warnings = []
        
        # 1. Extract Entities using NER
        # Returns list of dicts: [{'entity_group': 'Medication', 'word': 'Panadol', ...}]
        entities = self.ner_pipeline(summary_text)
        
        # 2. Separate entities into Drugs and Dosages
        drugs = []
        dosages = []
        
        for ent in entities:
            label = ent['entity_group']
            
            # The model 'd4data/biomedical-ner-all' uses specific labels:
            # 'Medication': Drug names
            # 'Dosage': Strength or Amount (e.g., "500mg")
            if label == "Medication":
                drugs.append(ent)
            elif label == "Dosage": 
                dosages.append(ent)

        # 3. Entity Linking (Proximity Heuristic)
        # Iterate through found drugs and find the nearest dosage info.
        for drug in drugs:
            drug_name = drug['word'].lower().strip()
            
            # Check if this drug exists in our Knowledge Graph
            kg_node = self.drug_knowledge_graph.get(drug_name)
            if not kg_node:
                continue # Skip unknown drugs (or flag as 'Unknown Drug' in future)

            # Find the dosage entity closest to this drug in the text
            best_dosage_ent = self._find_closest_dosage(drug, dosages)
            
            if best_dosage_ent:
                # 4. Parse Dosage & Check Limit
                try:
                    # Extract numeric value and unit
                    amount, unit = self._parse_dosage_string(best_dosage_ent['word'])
                    
                    # Normalize unit (convert grams to milligrams)
                    if unit == 'g': 
                        amount *= 1000
                    
                    limit = kg_node['limit']
                    
                    # 5. Compare against Safety Limit
                    if amount > limit:
                        warnings.append(
                            f"🚨 SAFETY ALERT: {drug['word']} dosage ({amount}mg) "
                            f"exceeds standard daily limit ({limit}mg)."
                        )
                except ValueError:
                    # Logic to handle cases where dosage string isn't parseable (e.g., "two tablets")
                    continue 

        return warnings

    async def check_safety(self, summary_text: str) -> List[str]:
        """
        [PUBLIC/ASYNC] Performs a comprehensive safety assessment on the provided text.
        Offloads the synchronous rule detection logic to a thread to prevent blocking.
        """
        return await asyncio.to_thread(self._detect_rule_violations, summary_text)    

    def _find_closest_dosage(self, drug_ent: Dict, dosage_list: List[Dict]) -> Optional[Dict]:
        """
        Finds the dosage entity physically closest to the drug entity in text
        using character index positions.
        """
        if not dosage_list:
            return None
            
        # Calculate center position of the drug entity
        drug_pos = (drug_ent['start'] + drug_ent['end']) / 2
        
        closest_dosage = None
        min_dist = float('inf')
        
        for dosage in dosage_list:
            # Calculate center position of the dosage entity
            dose_pos = (dosage['start'] + dosage['end']) / 2
            dist = abs(drug_pos - dose_pos)
            
            # Heuristic: Dosage must be within 50 characters of the drug name
            # to be considered related.
            if dist < min_dist and dist < 50:
                min_dist = dist
                closest_dosage = dosage
                
        return closest_dosage

    def _parse_dosage_string(self, dosage_str: str) -> Tuple[int, str]:
        """
        Parses strings like "500mg", "1g", "500 mg" into (500, 'mg').
        Uses Regex for pattern matching.
        """
        # Regex to find digits followed optionally by space and unit (mg or g)
        match = re.search(r"(\d+)\s*(mg|g)", dosage_str.lower())
        
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            return value, unit
            
        raise ValueError(f"Invalid dosage format: {dosage_str}")

# Singleton Instance
safety_service = ClinicalSafetyService()