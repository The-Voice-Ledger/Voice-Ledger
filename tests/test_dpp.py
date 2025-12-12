"""
DPP (Digital Product Passport) Tests

Tests DPP generation, validation, and resolution.
"""

import pytest
from pathlib import Path

from dpp.dpp_builder import build_dpp, validate_dpp, save_dpp
from twin.twin_builder import record_anchor, record_token, record_settlement, get_batch_twin


def test_dpp_builder():
    """Test DPP building from digital twin"""
    batch_id = "BATCH-DPP-TEST-001"
    
    # Create minimal digital twin with settlement
    record_anchor(
        batch_id=batch_id,
        event_hash="c" * 64,
        event_type="commissioning"
    )
    
    record_token(
        batch_id=batch_id,
        token_id=200,
        quantity=100,
        metadata={"origin": "Ethiopia", "cooperative": "Test Coop"}
    )
    
    record_settlement(
        batch_id=batch_id,
        amount=1000000,
        recipient="0xTest"
    )
    
    # Build DPP
    dpp = build_dpp(
        batch_id=batch_id,
        product_name="Test Coffee",
        variety="Arabica",
        process_method="Washed",
        country="ET",
        region="Test Region",
        cooperative="Test Coop"
    )
    
    # Verify structure
    assert dpp["passportId"] == f"DPP-{batch_id}"
    assert dpp["batchId"] == batch_id
    assert dpp["version"] == "1.0.0"
    assert "productInformation" in dpp
    assert "traceability" in dpp
    assert "dueDiligence" in dpp
    assert "blockchain" in dpp


def test_dpp_validation():
    """Test DPP validation"""
    batch_id = "BATCH-DPP-TEST-002"
    
    # Create twin and DPP
    record_anchor(batch_id=batch_id, event_hash="d" * 64, event_type="commissioning")
    record_token(batch_id=batch_id, token_id=201, quantity=50, metadata={})
    record_settlement(batch_id=batch_id, amount=500000, recipient="0xTest2")
    
    dpp = build_dpp(
        batch_id=batch_id,
        product_name="Test Coffee 2",
        country="ET",
        region="Test Region 2",
        cooperative="Test Coop 2"
    )
    
    # Should pass validation
    is_valid, errors = validate_dpp(dpp)
    assert is_valid
    assert len(errors) == 0


def test_dpp_missing_fields():
    """Test DPP validation with missing required fields"""
    # Create invalid DPP (missing required fields)
    invalid_dpp = {
        "passportId": "DPP-TEST",
        "batchId": "BATCH-TEST"
        # Missing many required fields
    }
    
    is_valid, errors = validate_dpp(invalid_dpp)
    assert not is_valid
    assert len(errors) > 0


def test_dpp_eudr_compliance():
    """Test EUDR compliance fields in DPP"""
    batch_id = "BATCH-DPP-TEST-003"
    
    record_anchor(batch_id=batch_id, event_hash="e" * 64, event_type="commissioning")
    record_token(batch_id=batch_id, token_id=202, quantity=75, metadata={})
    record_settlement(batch_id=batch_id, amount=750000, recipient="0xTest3")
    
    dpp = build_dpp(
        batch_id=batch_id,
        product_name="EUDR Test Coffee",
        country="ET",
        region="Test Region",
        cooperative="Test Coop",
        deforestation_risk="low",
        eudr_compliant=True
    )
    
    # Verify EUDR fields
    assert dpp["dueDiligence"]["eudrCompliant"] is True
    assert dpp["dueDiligence"]["riskAssessment"]["deforestationRisk"] == "low"
    assert "assessmentDate" in dpp["dueDiligence"]["riskAssessment"]


def test_dpp_persistence():
    """Test DPP saving and loading"""
    batch_id = "BATCH-DPP-TEST-004"
    
    record_anchor(batch_id=batch_id, event_hash="f" * 64, event_type="commissioning")
    record_token(batch_id=batch_id, token_id=203, quantity=60, metadata={})
    record_settlement(batch_id=batch_id, amount=600000, recipient="0xTest4")
    
    dpp = build_dpp(
        batch_id=batch_id,
        product_name="Persistence Test Coffee",
        country="ET",
        region="Test Region",
        cooperative="Test Coop"
    )
    
    # Save DPP
    saved_path = save_dpp(dpp)
    assert saved_path.exists()
    assert saved_path.name == f"{batch_id}_dpp.json"
    
    # Load and verify
    import json
    with open(saved_path) as f:
        loaded_dpp = json.load(f)
    
    assert loaded_dpp["passportId"] == dpp["passportId"]
    assert loaded_dpp["batchId"] == dpp["batchId"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
