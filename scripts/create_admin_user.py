#!/usr/bin/env python3
"""
Create Admin User

Creates the first admin user for Voice Ledger system.
This user can approve other registrations.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import SessionLocal
from database.models import UserIdentity
from ssi.did.did_key import generate_did_key
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()


def create_admin_user(telegram_user_id: str, username: str = None, first_name: str = None):
    """
    Create an admin user with full privileges.
    
    Args:
        telegram_user_id: Telegram user ID
        username: Telegram username (optional)
        first_name: Telegram first name (optional)
    """
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == telegram_user_id
        ).first()
        
        if existing_user:
            # Update to admin if not already
            if existing_user.role != 'ADMIN':
                existing_user.role = 'ADMIN'
                existing_user.is_approved = True
                existing_user.approved_at = datetime.utcnow()
                db.commit()
                print(f"✅ Updated user {telegram_user_id} to ADMIN role")
            else:
                print(f"ℹ️  User {telegram_user_id} is already an ADMIN")
            
            print(f"\nAdmin Details:")
            print(f"  Telegram ID: {existing_user.telegram_user_id}")
            print(f"  Username: {existing_user.telegram_username}")
            print(f"  Name: {existing_user.telegram_first_name} {existing_user.telegram_last_name or ''}")
            print(f"  DID: {existing_user.did}")
            print(f"  Role: {existing_user.role}")
            print(f"  Language: {existing_user.preferred_language}")
            print(f"  Approved: {existing_user.is_approved}")
            return existing_user
        
        # Create new admin user
        print(f"Creating new ADMIN user for Telegram ID: {telegram_user_id}")
        
        # Generate DID keypair
        keypair = generate_did_key()
        
        # Get encryption key for private key storage (uses APP_SECRET_KEY)
        secret = os.getenv("APP_SECRET_KEY", "voice-ledger-default-secret-change-in-production")
        from hashlib import sha256
        import base64
        key_material = sha256(secret.encode()).digest()
        encryption_key = base64.urlsafe_b64encode(key_material)
        
        from cryptography.fernet import Fernet
        cipher_suite = Fernet(encryption_key)
        encrypted_private_key = cipher_suite.encrypt(base64.b64decode(keypair['private_key_b64'])).decode()
        
        # Create user
        admin_user = UserIdentity(
            telegram_user_id=telegram_user_id,
            telegram_username=username,
            telegram_first_name=first_name or "Admin",
            telegram_last_name="User",
            did=keypair['did'],
            encrypted_private_key=encrypted_private_key,
            public_key=keypair['public_key_b64'],
            role='ADMIN',
            is_approved=True,
            approved_at=datetime.utcnow(),
            preferred_language='en',
            language_set_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"\n✅ Admin user created successfully!")
        print(f"\nAdmin Details:")
        print(f"  Telegram ID: {admin_user.telegram_user_id}")
        print(f"  Username: {admin_user.telegram_username}")
        print(f"  Name: {admin_user.telegram_first_name} {admin_user.telegram_last_name}")
        print(f"  DID: {admin_user.did}")
        print(f"  Role: {admin_user.role}")
        print(f"  Language: {admin_user.preferred_language}")
        print(f"  Approved: {admin_user.is_approved}")
        
        print(f"\n📝 Next Steps:")
        print(f"  1. Set ADMIN_TELEGRAM_USER_ID={telegram_user_id} in .env file")
        print(f"  2. Restart services to apply changes")
        print(f"  3. Use /admin command in Telegram to manage registrations")
        
        return admin_user
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create admin user for Voice Ledger')
    parser.add_argument('telegram_user_id', help='Telegram user ID of the admin')
    parser.add_argument('--username', help='Telegram username', default=None)
    parser.add_argument('--first-name', help='First name', default='Admin')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Voice Ledger - Create Admin User")
    print("=" * 70)
    
    create_admin_user(
        telegram_user_id=args.telegram_user_id,
        username=args.username,
        first_name=args.first_name
    )
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    main()
