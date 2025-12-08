import sys
import os

# Add the project root to sys.path to import backend modules
# Assuming this script is placed in the project root directory
sys.path.append(os.getcwd())

try:
    from backend.services.safety import safety_service
except ImportError:
    print("❌ Error: Could not import 'safety_service'. Make sure you are running this from the project root.")
    sys.exit(1)

def run_safety_tests():
    """
    Runs various test cases to verify the logic of ClinicalSafetyService.
    """
    print("🧪 Starting Clinical Safety Service Tests...\n")

    test_cases = [
        # 1. Normal Case (Safe)
        {
            "name": "✅ Safe Dosage (Panadol)",
            "input": "Patient is prescribed Panadol 500mg twice daily for pain.",
            "expected_warning": False
        },
        # 2. Overdose Case (Exceeds Limit)
        # Panadol limit is 4000mg. 5000mg should trigger a warning.
        {
            "name": "🚨 Overdose (Panadol > 4000mg)",
            "input": "Patient accidentally ingested Panadol 5000mg this morning.",
            "expected_warning": True
        },
        # 3. Unit Conversion Case (Gram to Milligram)
        # 5g = 5000mg, which exceeds the 4000mg limit.
        {
            "name": "⚖️ Unit Conversion (5g -> 5000mg)",
            "input": "Current medication includes Panadol 5g daily.",
            "expected_warning": True
        },
        # 4. Multiple Drugs Case
        # Ibuprofen limit is 3200mg (4000mg is unsafe).
        # Amoxicillin limit is 3000mg (500mg is safe).
        {
            "name": "💊 Multiple Drugs (One Unsafe, One Safe)",
            "input": "Patient takes Ibuprofen 4000mg and Amoxicillin 500mg.",
            "expected_warning": True # Should warn about Ibuprofen
        },
        # 5. Distance Heuristic Case (Too far to match)
        # The dosage is more than 50 chars away, so it should be ignored (No warning).
        {
            "name": "📏 Distance Heuristic (Dosage too far)",
            "input": "Patient takes Panadol because of a very long and complicated history of chronic back pain which is treated with 5000mg.",
            "expected_warning": False 
        },
        # 6. Unknown Drug Case
        # 'UnknownDrug' is not in the Knowledge Graph, so it should be ignored.
        {
            "name": "❓ Unknown Drug",
            "input": "Prescribed UnknownDrug 9000mg.",
            "expected_warning": False
        }
    ]

    for case in test_cases:
        print(f"🔹 Testing: {case['name']}")
        print(f"   Input: \"{case['input']}\"")
        
        # Execute the safety check
        warnings = safety_service.check_safety(case['input'])
        
        # Validation Logic
        has_warning = len(warnings) > 0
        status = "PASS" if has_warning == case['expected_warning'] else "FAIL"
        
        # Print Result
        if has_warning:
            for w in warnings:
                print(f"   ⚠️  Output: {w}")
        else:
            print(f"   ✅ Output: No warnings found.")
            
        print(f"   Result: {status}\n")

if __name__ == "__main__":
    # Ensure the pipeline is loaded before running tests
    run_safety_tests()
