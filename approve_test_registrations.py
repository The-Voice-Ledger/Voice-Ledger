"""
Quick script to approve test registrations via API
"""

import requests

BASE_URL = "http://localhost:8000"

# Approve exporter (REG-0011)
print("Approving REG-0011 (Exporter)...")
response = requests.post(f"{BASE_URL}/admin/registrations/11/approve")
print(f"Status: {response.status_code}")

# Approve buyer (REG-0012)
print("Approving REG-0012 (Buyer)...")
response = requests.post(f"{BASE_URL}/admin/registrations/12/approve")
print(f"Status: {response.status_code}")

print("\n✅ Approvals completed!")
print("Now run: python test_multi_actor_registration.py --verify 11 12")
