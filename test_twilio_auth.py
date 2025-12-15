"""
Quick test script to verify Twilio credentials.
"""
import os
from dotenv import dotenv_values
from twilio.rest import Client

# Load environment variables
env = dotenv_values('.env')

def test_twilio_auth():
    """Test Twilio authentication and account info."""
    account_sid = env.get("TWILIO_ACCOUNT_SID")
    auth_token = env.get("TWILIO_AUTH_TOKEN")
    phone_number = env.get("TWILIO_PHONE_NUMBER")
    
    print("🔐 Testing Twilio Authentication...")
    print(f"   Account SID: {account_sid}")
    print(f"   Phone Number: {phone_number}")
    
    try:
        # Initialize client
        client = Client(account_sid, auth_token)
        
        # Fetch account info
        account = client.api.accounts(account_sid).fetch()
        
        print(f"\n✅ Authentication Successful!")
        print(f"   Account Status: {account.status}")
        print(f"   Account Type: {account.type}")
        print(f"   Friendly Name: {account.friendly_name}")
        
        # List available phone numbers
        print(f"\n📱 Checking phone numbers...")
        numbers = client.incoming_phone_numbers.list(limit=5)
        if numbers:
            for number in numbers:
                print(f"   • {number.phone_number} ({number.friendly_name})")
        else:
            print(f"   No phone numbers found. You may need to provision one.")
            
        return True
        
    except Exception as e:
        print(f"\n❌ Authentication Failed: {e}")
        return False

if __name__ == "__main__":
    test_twilio_auth()
