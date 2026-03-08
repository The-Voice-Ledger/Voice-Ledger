
import os
from database import get_db
from database.crud import create_batch, get_batch_by_batch_id
from dpp.dpp_builder import build_dpp

def test_qr_code_storage_and_dpp():
    """Test that QR codes are generated during batch creation and served via DPP."""
    batch_id = "TEST-QR-BATCH-001"
    
    # Cleanup if exists
    with get_db() as db:
        from database.models import CoffeeBatch, EPCISEvent
        b = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
        if b:
            db.query(EPCISEvent).filter_by(batch_id=b.id).delete()
            db.delete(b)
            db.commit()

    # 1. Create batch
    batch_data = {
        "batch_id": batch_id,
        "gtin": "01234567890123",
        "batch_number": "QR-001",
        "quantity_kg": 100,
        "variety": "Arabica",
        "origin_country": "ET",
        "origin_region": "Guji"
    }
    
    with get_db() as db:
        batch = create_batch(db, batch_data)
        assert batch.qr_code_base64 is not None
        assert len(batch.qr_code_base64) > 100
        print(f"✓ QR code stored in DB: {len(batch.qr_code_base64)} chars")

    # 2. Build DPP and check QR
    dpp = build_dpp(batch_id=batch_id)
    assert "qrCode" in dpp
    assert dpp["qrCode"]["imageUrl"].startswith("data:image/png;base64,")
    print("✓ DPP contains QR code image data")

    # 3. Test legacy batch (missing QR)
    legacy_id = "TEST-LEGACY-BATCH-001"
    with get_db() as db:
        # Manually insert without QR
        from database.models import CoffeeBatch
        b = db.query(CoffeeBatch).filter_by(batch_id=legacy_id).first()
        if b:
            db.delete(b)
            db.commit()
            
        b = CoffeeBatch(
            batch_id=legacy_id,
            gtin="91234567890123",
            batch_number="LEG-001",
            quantity_kg=50,
            qr_code_base64=None
        )
        db.add(b)
        db.commit()
    
    # Building DPP should trigger auto-generation and save to DB
    dpp_legacy = build_dpp(batch_id=legacy_id)
    assert dpp_legacy["qrCode"]["imageUrl"].startswith("data:image/png;base64,")
    
    with get_db() as db:
        b_updated = db.query(CoffeeBatch).filter_by(batch_id=legacy_id).first()
        assert b_updated.qr_code_base64 is not None
        print("✓ Legacy batch auto-generated and saved QR code")

    # Cleanup
    with get_db() as db:
        from database.models import CoffeeBatch
        db.query(CoffeeBatch).filter(CoffeeBatch.batch_id.in_([batch_id, legacy_id])).delete()
        db.commit()

if __name__ == "__main__":
    test_qr_code_storage_and_dpp()
