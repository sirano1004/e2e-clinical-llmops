import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple
# from transformers import pipeline # Removed unused import
from ..core.logger import logger
# Assuming settings import is available if needed, otherwise removed for simplicity

class ClinicalSafetyService:
    """
    Clinical Safety Layer (Rule-Based + Knowledge Graph).
    
    This service is designed to be a placeholder for a robust graph database check,
    performing dosage verification against a hard-coded set of limits.
    
    Architecture:
    1. Extraction: Simulated extraction of Medication and Dosage entities via regex.
    2. Verification: Checks extracted dosage against the hard-coded Knowledge Graph limits.
    """

    def __init__(self):
        logger.info("🛡️ Initializing Clinical Safety Layer (Rule-Based KG)...")
        
        # 1. Knowledge Graph (In-Memory Limits)
        # Key: Normalized Drug Name (lowercase)
        # Value: Safety constraints (limit in mg per day)
        self.drug_knowledge_graph = {
            "panadol": {"limit": 4000, "unit": "mg"},
            "paracetamol": {"limit": 4000, "unit": "mg"},
            "ibuprofen": {"limit": 3200, "unit": "mg"},
            "amoxicillin": {"limit": 3000, "unit": "mg"},
            "metformin": {"limit": 2550, "unit": "mg"},
            "aspirin": {"limit": 4000, "unit": "mg"}
        }
        
        # [Removed] NER Pipeline loading is unnecessary since it's a placeholder.
        self.ner_pipeline = None 
        logger.info("✅ Safety rules loaded and ready (CPU-only).")


    def _detect_rule_violations(self, summary_text: str) -> List[str]:
        """
        Main entry point. Scans text for safety violations based on rules.
        """
        warnings = []
        
        # 1. Simulated Entity Extraction (using regex over NER model)
        # We search for known drug names followed by dosage information (simulating NER linking).
        
        # Regex: Finds a known drug (group 1) followed by a quantity and unit (group 2: 500mg, 1g)
        # Pattern example: "prescribe Ibuprofen 600mg every day"
        for drug_name in self.drug_knowledge_graph.keys():
            # Pattern: (Drug Name) (Optional Space) (Dosage String)
            pattern = rf"\b({re.escape(drug_name)})\s*(\d+\s*(?:mg|g))\b"
            
            # Find all potential drug-dosage pairs
            for match in re.finditer(pattern, summary_text.lower()):
                matched_drug = match.group(1).strip()
                dosage_str = match.group(2).strip()
                
                kg_node = self.drug_knowledge_graph.get(matched_drug)
                
                # This should always be true if we iterated over the keys, but safe check
                if not kg_node:
                    continue 

                # 2. Parse Dosage & Check Limit
                try:
                    amount, unit = self._parse_dosage_string(dosage_str)
                    
                    # Normalize unit (convert grams to milligrams)
                    if unit == 'g': 
                        amount *= 1000
                    
                    limit = kg_node['limit']
                    
                    # 3. Compare against Safety Limit
                    if amount > limit:
                        warnings.append(
                            f"🚨 SAFETY ALERT: Potential overdose risk. {matched_drug.capitalize()} dosage ({amount}mg) "
                            f"exceeds standard daily limit ({limit}mg)."
                        )
                except ValueError:
                    # Ignore unparseable dosage strings
                    logger.debug(f"DEBUG: Could not parse dosage string '{dosage_str}' for {matched_drug}.")
                    continue 

        return warnings

    async def assess_safety_risks(self, summary_text: str) -> List[str]:
        """
        [PUBLIC/ASYNC] Performs a comprehensive safety assessment on the provided text.
        Offloads the synchronous rule detection logic to a thread to prevent blocking.
        """
        return await asyncio.to_thread(self._detect_rule_violations, summary_text)    

    # [Removed] _find_closest_dosage is no longer needed since the main regex links drug and dosage.
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