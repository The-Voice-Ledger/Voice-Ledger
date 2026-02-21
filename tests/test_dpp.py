"""
DPP (Digital Product Passport) Tests

Tests DPP generation, validation, and resolution.
"""

import pytest
from pathlib import Path

from dpp.dpp_builder import build_dpp, validate_dpp, save_dpp
from twin.twin_builder import record_anchor, record_token, record_settlement, get_batch_twin


# --- DB helpers for test data ---------------------------------------------------

def _create_test_batch(db, batch_id, farmer_id_str="FARMER-DPP-TEST"):
    from database.models import FarmerIdentity, CoffeeBatch
    from gs1.identifiers import gtin as gs1_gtin
    import hashlib

    def _num(s):
        d = "".join(c for c in s if c.isdigit())
        return d[:9] if d else str(int(hashlib.md5(s.encode()).hexdigest(), 16))[:9]

    farmer = db.query(FarmerIdentity).filter_by(farmer_id=farmer_id_str).first()
    if not farmer:
        farmer = FarmerIdentity(
            farmer_id=farmer_id_str, did=f"did:key:dpp-test-{farmer_id_str}",
            encrypted_private_key="k", public_key="pk",
            name="DPP Test Farmer", region="Guji",
        )
        db.add(farmer)
        db.flush()

    batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
    if not batch:
        batch = CoffeeBatch(
            batch_id=batch_id, gtin=gs1_gtin(_num(batch_id)),
            batch_number=batch_id, quantity_kg=100,
            origin_region="Guji", origin_country="ET",
            farm_name="Test Co-op", variety="Heirloom",
            process_method="Washed", quality_grade="Q1",
            farmer_id=farmer.id,
        )
        db.add(batch)
        db.flush()
    db.commit()
    return farmer, batch


def _cleanup(db, batch_ids, farmer_id_str="FARMER-DPP-TEST"):
    from database.models import CoffeeBatch, EPCISEvent, FarmerIdentity
    try:
        db.rollback()
    except Exception:
        pass
    for bid in batch_ids:
        b = db.query(CoffeeBatch).filter_by(batch_id=bid).first()
        if b:
            db.query(EPCISEvent).filter_by(batch_id=b.id).delete()
            db.delete(b)
    f = db.query(FarmerIdentity).filter_by(farmer_id=farmer_id_str).first()
    if f:
        db.query(CoffeeBatch).filter_by(farmer_id=f.id).delete()
        db.delete(f)
    db.commit()


# --- Tests -----------------------------------------------------------------------


def test_dpp_builder():
    """Test DPP building from digital twin"""
    from database import get_db
    batch_id = "BATCH-DPP-TEST-001"

    with get_db() as db:
        _create_test_batch(db, batch_id)

    try:
        record_token(batch_id=batch_id, token_id=200, quantity=100,
                     metadata={"origin": "Ethiopia", "cooperative": "Test Coop"})

        dpp = build_dpp(
            batch_id=batch_id, product_name="Test Coffee",
            variety="Arabica", process_method="Washed",
            country="ET", region="Test Region", cooperative="Test Coop",
        )

        assert dpp["passportId"] == f"DPP-{batch_id}"
        assert dpp["batchId"] == batch_id
        assert dpp["version"] == "3.0.0"  # v3: EUDR GPS verification + Chainlink DON attestation
        assert "productInformation" in dpp
        assert "traceability" in dpp
        assert "dueDiligence" in dpp
        assert "blockchain" in dpp
    finally:
        with get_db() as db:
            _cleanup(db, [batch_id])


def test_dpp_validation():
    """Test DPP validation"""
    from database import get_db
    batch_id = "BATCH-DPP-TEST-002"

    with get_db() as db:
        _create_test_batch(db, batch_id)

    try:
        record_token(batch_id=batch_id, token_id=201, quantity=50, metadata={})

        dpp = build_dpp(
            batch_id=batch_id, product_name="Test Coffee 2",
            country="ET", region="Test Region 2", cooperative="Test Coop 2",
        )

        is_valid, errors = validate_dpp(dpp)
        assert is_valid
        assert len(errors) == 0
    finally:
        with get_db() as db:
            _cleanup(db, [batch_id])


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
    from database import get_db
    batch_id = "BATCH-DPP-TEST-003"

    with get_db() as db:
        _create_test_batch(db, batch_id)

    try:
        record_token(batch_id=batch_id, token_id=202, quantity=75, metadata={})

        dpp = build_dpp(
            batch_id=batch_id, product_name="EUDR Test Coffee",
            country="ET", region="Test Region", cooperative="Test Coop",
            deforestation_risk="low", eudr_compliant=True,
        )

        assert dpp["dueDiligence"]["eudrCompliant"] is True
        assert dpp["dueDiligence"]["riskAssessment"]["deforestationRisk"] == "low"
        assert "assessmentDate" in dpp["dueDiligence"]["riskAssessment"]
    finally:
        with get_db() as db:
            _cleanup(db, [batch_id])


def test_dpp_persistence():
    """Test DPP saving and loading"""
    from database import get_db
    batch_id = "BATCH-DPP-TEST-004"

    with get_db() as db:
        _create_test_batch(db, batch_id)

    try:
        record_token(batch_id=batch_id, token_id=203, quantity=60, metadata={})

        dpp = build_dpp(
            batch_id=batch_id, product_name="Persistence Test Coffee",
            country="ET", region="Test Region", cooperative="Test Coop",
        )

        saved_path = save_dpp(dpp)
        assert saved_path.exists()
        assert saved_path.name == f"{batch_id}_dpp.json"

        import json
        with open(saved_path) as f:
            loaded_dpp = json.load(f)

        assert loaded_dpp["passportId"] == dpp["passportId"]
        assert loaded_dpp["batchId"] == dpp["batchId"]
    finally:
        with get_db() as db:
            _cleanup(db, [batch_id])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
