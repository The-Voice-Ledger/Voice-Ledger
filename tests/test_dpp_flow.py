"""
End-to-End DPP Flow Test

Tests the complete Digital Product Passport workflow:
1. Create EPCIS event
2. Build digital twin
3. Generate DPP
4. Create QR code
5. Resolve DPP via API
"""

import json
from pathlib import Path

# Import modules from the project
from gs1.identifiers import sscc
from epcis.epcis_builder import create_commission_event
from epcis.hash_event import hash_event
from twin.twin_builder import record_anchor, record_token, record_settlement, get_batch_twin
from dpp.dpp_builder import build_dpp, validate_dpp, save_dpp
from dpp.qrcode_gen import generate_qr_code, create_labeled_qr_code


def test_complete_dpp_flow():
    """Test complete DPP workflow from event to QR code"""
    
    print("=" * 60)
    print("🧪 TESTING COMPLETE DPP FLOW")
    print("=" * 60)
    print()
    
    # Step 1: Create EPCIS event
    print("📝 Step 1: Creating EPCIS commissioning event...")
    batch_id = "BATCH-2025-TEST"
    event_file = create_commission_event(batch_id)
    print(f"   ✅ Event created: {event_file}")
    print()
    
    # Step 2: Hash the event
    print("🔐 Step 2: Hashing EPCIS event...")
    event_hash = hash_event(event_file)
    print(f"   ✅ Event hash: {event_hash}")
    print()
    
    # Step 3: Build digital twin
    print("🔗 Step 3: Building digital twin...")
    
    # Record event anchor
    record_anchor(
        batch_id=batch_id,
        event_hash=event_hash,
        event_type="commissioning",
        tx_hash="0xabc123..."  # Would be real tx hash from blockchain
    )
    print("   ✅ Recorded event anchor")
    
    # Record token minting
    record_token(
        batch_id=batch_id,
        token_id=42,
        quantity=100,
        metadata={
            "origin": "Ethiopia",
            "region": "Yirgacheffe",
            "cooperative": "Test Cooperative",
            "variety": "Arabica",
            "processMethod": "Washed"
        }
    )
    print("   ✅ Recorded token minting")
    
    # Record settlement
    record_settlement(
        batch_id=batch_id,
        amount=2500000,
        recipient="0xTestRecipient123456789"
    )
    print("   ✅ Recorded settlement")
    print()
    
    # Verify digital twin
    print("🔍 Step 4: Verifying digital twin...")
    twin = get_batch_twin(batch_id)
    if twin:
        print(f"   ✅ Digital twin found")
        print(f"      - Batch ID: {twin['batchId']}")
        print(f"      - Token ID: {twin['tokenId']}")
        print(f"      - Quantity: {twin['quantity']} bags")
        print(f"      - Anchors: {len(twin['anchors'])} events")
        print(f"      - Settlement: ${twin['settlement']['amount']/100:.2f}")
    else:
        print("   ❌ Digital twin not found")
        return False
    print()
    
    # Step 5: Build DPP
    print("📄 Step 5: Building Digital Product Passport...")
    try:
        dpp = build_dpp(
            batch_id=batch_id,
            product_name="Ethiopian Yirgacheffe - Test Batch",
            variety="Arabica",
            process_method="Washed",
            country="ET",
            region="Yirgacheffe, Gedeo Zone",
            cooperative="Test Cooperative",
            deforestation_risk="none",
            eudr_compliant=True
        )
        print(f"   ✅ DPP built: {dpp['passportId']}")
        print(f"      - Product: {dpp['productInformation']['productName']}")
        print(f"      - Quantity: {dpp['productInformation']['quantity']} {dpp['productInformation']['unit']}")
        print(f"      - EUDR Compliant: {dpp['dueDiligence']['eudrCompliant']}")
        print(f"      - Events: {len(dpp['traceability']['events'])}")
    except Exception as e:
        print(f"   ❌ DPP build failed: {e}")
        return False
    print()
    
    # Step 6: Validate DPP
    print("✅ Step 6: Validating DPP...")
    is_valid, errors = validate_dpp(dpp)
    if is_valid:
        print("   ✅ DPP validation passed")
    else:
        print("   ❌ DPP validation failed:")
        for error in errors:
            print(f"      - {error}")
        return False
    print()
    
    # Step 7: Save DPP
    print("💾 Step 7: Saving DPP...")
    dpp_file = save_dpp(dpp)
    print(f"   ✅ DPP saved to: {dpp_file}")
    print()
    
    # Step 8: Generate QR codes
    print("📱 Step 8: Generating QR codes...")
    
    # Simple QR code
    qr_output = Path(__file__).parent.parent / "dpp" / "qrcodes" / f"{batch_id}_qr.png"
    base64_img, qr_path = generate_qr_code(
        batch_id=batch_id,
        resolver_base_url="https://dpp.voiceledger.io",
        output_file=qr_output
    )
    print(f"   ✅ QR code generated: {qr_path}")
    
    # Labeled QR code
    labeled_qr_output = Path(__file__).parent.parent / "dpp" / "qrcodes" / f"{batch_id}_labeled_qr.png"
    labeled_path = create_labeled_qr_code(
        batch_id=batch_id,
        product_name="Ethiopian Yirgacheffe",
        resolver_base_url="https://dpp.voiceledger.io",
        output_file=labeled_qr_output
    )
    print(f"   ✅ Labeled QR code generated: {labeled_path}")
    print()
    
    # Step 9: Summary
    print("=" * 60)
    print("✅ COMPLETE DPP FLOW TEST PASSED")
    print("=" * 60)
    print()
    print("📊 Summary:")
    print(f"   • Batch ID: {batch_id}")
    print(f"   • EPCIS Event: {event_file.name}")
    print(f"   • Event Hash: {event_hash[:16]}...")
    print(f"   • Token ID: {twin['tokenId']}")
    print(f"   • DPP: {dpp_file.name}")
    print(f"   • QR Code: {qr_path.name}")
    print(f"   • Resolver URL: {dpp['qrCode']['url']}")
    print()
    print("🎯 Next Steps:")
    print("   1. Deploy contracts to local Anvil node")
    print("   2. Record actual blockchain transactions")
    print("   3. Test DPP resolver API with real data")
    print("   4. Print QR codes for physical packaging")
    print()
    
    return True


if __name__ == "__main__":
    success = test_complete_dpp_flow()
    exit(0 if success else 1)
