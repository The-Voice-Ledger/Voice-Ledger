"""
Test RFQ Marketplace API Endpoints (Lab 15)

Tests complete RFQ workflow:
1. Buyer creates RFQ
2. Cooperative submits offer
3. Buyer views offers
4. Buyer accepts offer
5. Verify acceptance

Prerequisites:
- Buyer user (ID from test_marketplace_registration.py - user_id=5)
- Cooperative user (existing cooperative manager from database)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from datetime import datetime, timedelta
from database.models import SessionLocal, UserIdentity

API_BASE = "http://localhost:8000/api"

def test_rfq_workflow():
    """Test complete RFQ workflow"""
    print("=" * 70)
    print("LAB 15: RFQ Marketplace API Test")
    print("=" * 70)
    
    db = SessionLocal()
    
    try:
        # Get buyer user (from Lab 14 tests - test_buyer)
        buyer = db.query(UserIdentity).filter_by(
            telegram_username="test_buyer",
            role="BUYER"
        ).first()
        
        if not buyer:
            print("❌ No buyer found. Run test_marketplace_registration.py first!")
            return False
        
        buyer_id = buyer.id
        print(f"\n✓ Found buyer: {buyer.telegram_username} (ID: {buyer_id})")
        
        # Get cooperative user
        coop_manager = db.query(UserIdentity).filter_by(
            role="COOPERATIVE_MANAGER",
            is_approved=True
        ).first()
        
        if not coop_manager:
            print("❌ No cooperative manager found!")
            return False
        
        coop_id = coop_manager.id
        print(f"✓ Found cooperative: {coop_manager.telegram_username} (ID: {coop_id})")
        
        # Test 1: Create RFQ
        print("\n" + "=" * 70)
        print("Test 1: Create RFQ (Buyer)")
        print("=" * 70)
        
        rfq_data = {
            "quantity_kg": 5000,
            "variety": "Yirgacheffe",
            "processing_method": "Washed",
            "grade": "Grade 1",
            "delivery_location": "Rotterdam Port",
            "delivery_deadline": (datetime.now() + timedelta(days=60)).isoformat(),
            "additional_specs": {
                "cup_score_min": 85,
                "moisture_max": 12.5
            }
        }
        
        response = requests.post(
            f"{API_BASE}/rfq?user_id={buyer_id}",
            json=rfq_data
        )
        
        if response.status_code == 201:
            rfq = response.json()
            rfq_id = rfq['id']
            print(f"✅ RFQ created: {rfq['rfq_number']}")
            print(f"   Quantity: {rfq['quantity_kg']} kg")
            print(f"   Variety: {rfq['variety']}")
            print(f"   Status: {rfq['status']}")
        else:
            print(f"❌ Failed to create RFQ: {response.status_code}")
            print(response.text)
            return False
        
        # Test 2: List RFQs (Cooperative view)
        print("\n" + "=" * 70)
        print("Test 2: List RFQs (Cooperative Marketplace)")
        print("=" * 70)
        
        response = requests.get(f"{API_BASE}/rfqs?status=OPEN")
        
        if response.status_code == 200:
            rfqs = response.json()
            print(f"✅ Found {len(rfqs)} open RFQs")
            for rfq in rfqs[:3]:  # Show first 3
                print(f"   - {rfq['rfq_number']}: {rfq['quantity_kg']}kg {rfq['variety']}")
        else:
            print(f"❌ Failed to list RFQs: {response.status_code}")
            return False
        
        # Test 3: Submit Offer (Cooperative)
        print("\n" + "=" * 70)
        print("Test 3: Submit Offer (Cooperative)")
        print("=" * 70)
        
        offer_data = {
            "quantity_offered_kg": 5000,
            "price_per_kg": 4.50,
            "delivery_timeline": "45 days from contract",
            "quality_certifications": {
                "Organic": True,
                "Fair Trade": True
            }
        }
        
        response = requests.post(
            f"{API_BASE}/rfq/{rfq_id}/offer?user_id={coop_id}",
            json=offer_data
        )
        
        if response.status_code == 201:
            offer = response.json()
            offer_id = offer['id']
            print(f"✅ Offer submitted: {offer['offer_number']}")
            print(f"   Quantity: {offer['quantity_offered_kg']} kg")
            print(f"   Price: ${offer['price_per_kg']}/kg")
            print(f"   Total: ${offer['quantity_offered_kg'] * offer['price_per_kg']}")
        else:
            print(f"❌ Failed to submit offer: {response.status_code}")
            print(response.text)
            return False
        
        # Test 4: View Offers (Buyer)
        print("\n" + "=" * 70)
        print("Test 4: View Offers (Buyer)")
        print("=" * 70)
        
        response = requests.get(f"{API_BASE}/rfq/{rfq_id}/offers?user_id={buyer_id}")
        
        if response.status_code == 200:
            offers = response.json()
            print(f"✅ Found {len(offers)} offer(s)")
            for offer in offers:
                print(f"   - {offer['offer_number']}: {offer['cooperative_name']}")
                print(f"     ${offer['price_per_kg']}/kg × {offer['quantity_offered_kg']}kg = ${offer['price_per_kg'] * offer['quantity_offered_kg']}")
        else:
            print(f"❌ Failed to view offers: {response.status_code}")
            return False
        
        # Test 5: Accept Offer (Buyer)
        print("\n" + "=" * 70)
        print("Test 5: Accept Offer (Buyer)")
        print("=" * 70)
        
        acceptance_data = {
            "offer_id": offer_id,
            "quantity_accepted_kg": 5000,
            "payment_terms": "NET_30"
        }
        
        response = requests.post(
            f"{API_BASE}/rfq/{rfq_id}/accept?user_id={buyer_id}",
            json=acceptance_data
        )
        
        if response.status_code == 201:
            acceptance = response.json()
            print(f"✅ Offer accepted: {acceptance['acceptance_number']}")
            print(f"   Quantity: {acceptance['quantity_accepted_kg']} kg")
            print(f"   Payment: {acceptance['payment_status']}")
            print(f"   Delivery: {acceptance['delivery_status']}")
        else:
            print(f"❌ Failed to accept offer: {response.status_code}")
            print(response.text)
            return False
        
        # Test 6: List My Offers (Cooperative)
        print("\n" + "=" * 70)
        print("Test 6: List My Offers (Cooperative)")
        print("=" * 70)
        
        response = requests.get(f"{API_BASE}/offers?user_id={coop_id}")
        
        if response.status_code == 200:
            offers = response.json()
            print(f"✅ Found {len(offers)} offer(s) from this cooperative")
            for offer in offers:
                print(f"   - {offer['offer_number']}: {offer['status']}")
        else:
            print(f"❌ Failed to list offers: {response.status_code}")
            return False
        
        print("\n" + "=" * 70)
        print("✅ ALL RFQ WORKFLOW TESTS PASSED!")
        print("=" * 70)
        print(f"\nSummary:")
        print(f"  - RFQ created: {rfq['rfq_number']}")
        print(f"  - Offer submitted: {offer['offer_number']}")
        print(f"  - Acceptance: {acceptance['acceptance_number']}")
        print(f"  - Total value: ${offer['price_per_kg'] * acceptance['quantity_accepted_kg']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    success = test_rfq_workflow()
    sys.exit(0 if success else 1)
