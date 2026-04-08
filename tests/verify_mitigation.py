import json
import sys
import os
sys.path.append(os.getcwd())
from dataverse_agent.errors import MitigationManager, MitigationGuidance

def test_mitigation_manager():
    # Test 1: KeyError mitigation
    error = KeyError("column 'non_existent' not found in axis")
    guidance = MitigationManager.get_guidance(error)
    print(f"KeyError match: {guidance.friendly_message}")
    assert "columns" in guidance.friendly_message.lower()
    
    # Test 2: Generic exception
    error = RuntimeError("Something went wrong")
    guidance = MitigationManager.get_guidance(error)
    print(f"Generic match: {guidance.friendly_message}")
    assert "unexpected" in guidance.friendly_message.lower()

    # Test 3: Technical details present
    assert guidance.technical_details is not None
    print("Technical details captured correctly.")

if __name__ == "__main__":
    try:
        test_mitigation_manager()
        print("\n✅ Verification SUCCESS: MitigationManager is working correctly.")
    except Exception as e:
        print(f"\n❌ Verification FAILED: {e}")
