from typing import List
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from schemas import DialogueTurn

class MedicalPIIHandler:
    def __init__(self):
        # 1. Create a Registry to hold our custom logic
        registry = RecognizerRegistry()
        
        # Load standard English recognizers (Person, Date, Phone, etc.)
        registry.load_predefined_recognizers()

        # 2. Add Custom Medical Recognizers
        self._add_medical_id_recognizer(registry)
        self._add_provider_recognizer(registry)
        self._add_disease_allowlist(registry)

        # 3. Initialize Engines with our custom registry and the Spacy model
        self.analyzer = AnalyzerEngine(registry=registry, supported_languages=["en"])
        self.anonymizer = AnonymizerEngine()

    def _add_medical_id_recognizer(self, registry: RecognizerRegistry):
        """
        Catches MRN (Medical Record Numbers) or Insurance IDs.
        Regex: Looks for 'MRN', 'Id', '#' followed by digits.
        """
        mrn_pattern = Pattern(
            name="mrn_pattern",
            regex=r"(?i)\b(mrn|medical record|patient id|medicare no|id)[:\s#]*([0-9]{4,12})\b",
            score=0.95 # High confidence
        )
        mrn_recognizer = PatternRecognizer(
            supported_entity="MEDICAL_ID",
            patterns=[mrn_pattern]
        )
        registry.add_recognizer(mrn_recognizer)

    def _add_provider_recognizer(self, registry: RecognizerRegistry):
        """
        Catches Doctor names specifically.
        Context: 'Dr.', 'Doctor', 'Nurse'
        """
        provider_pattern = Pattern(
            name="provider_pattern",
            regex=r"(?i)\b(dr\.|doctor|nurse|prof\.)\s+([A-Z][a-z]+)\b",
            score=0.85
        )
        provider_recognizer = PatternRecognizer(
            supported_entity="MEDICAL_PROVIDER",
            patterns=[provider_pattern]
        )
        registry.add_recognizer(provider_recognizer)

    def _add_disease_allowlist(self, registry: RecognizerRegistry):
        """
        [CRITICAL] Prevents masking of diseases that sound like names.
        e.g., 'Parkinson', 'Alzheimer', 'Cushing', 'Addison'.
        We define them, but give them a score of 0.0 or handle logic to ignore.
        
        Actually, Presidio handles this by 'Deny Lists' inside PatternRecognizer 
        or by recognizing them as a different entity and NOT anonymizing that entity.
        """
        # Strategy: We register a "DISEASE" entity. 
        # Since we only ask Anonymizer to mask [PERSON, PHONE, MEDICAL_ID], 
        # these won't get masked even if the generic PERSON recognizer picks them up.
        diseases = [
            "Parkinson", "Alzheimer", "Addison", "Cushing", "Hodgkin", 
            "Crohn", "Hashimoto", "Lou Gehrig", "Down"
        ]
        
        disease_recognizer = PatternRecognizer(
            supported_entity="DISEASE_EPONYM",
            deny_list=diseases
        )
        registry.add_recognizer(disease_recognizer)

    def mask_dialogue(self, history: List[DialogueTurn]) -> List[DialogueTurn]:
        """
        Iterates through the dialogue history and masks sensitive entities.
        """
        masked_history = []
        
        # Entities we WANT to hide
        target_entities = [
            "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", 
            "MEDICAL_ID", "MEDICAL_PROVIDER", "LOCATION"
        ]

        for turn in history:
            # 1. Analyze
            results = self.analyzer.analyze(
                text=turn.content,
                entities=target_entities,
                language='en'
            )
            
            # Filter out conflicts: If "Parkinson" is detected as PERSON but also DISEASE_EPONYM,
            # we need logic. Ideally, Presidio prefers the custom one if scored higher.
            # For this MVP, relying on standard Anonymizer logic usually works well enough 
            # if we don't include "DISEASE_EPONYM" in the anonymizer list.

            # 2. Anonymize
            anonymized_result = self.anonymizer.anonymize(
                text=turn.content,
                analyzer_results=results,
                operators={
                    "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"}),
                    "PERSON": OperatorConfig("replace", {"new_value": "<PATIENT>"}),
                    "MEDICAL_PROVIDER": OperatorConfig("replace", {"new_value": "<DOCTOR>"}),
                    "MEDICAL_ID": OperatorConfig("replace", {"new_value": "<MRN>"}),
                    "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE>"}),
                }
            )

            # 3. Rebuild
            masked_history.append(DialogueTurn(
                role=turn.role,
                content=anonymized_result.text,
                timestamp=turn.timestamp
            ))

        return masked_history

# Singleton
pii_service = MedicalPIIHandler()