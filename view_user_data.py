import sys
import argparse
from datetime import datetime

# ANSI Color codes for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Ensure UTF-8 output for Windows terminals (avoid UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def get_db_and_models():
    from database.connection import get_db
    from database.models import UserIdentity, FarmerIdentity, CoffeeBatch, VerifiableCredential, Organization, FarmerCooperative
    return get_db, UserIdentity, FarmerIdentity, CoffeeBatch, VerifiableCredential, Organization, FarmerCooperative

def print_section(title):
    print(f"\n{BOLD}{BLUE}=== {title} ==={RESET}")

def print_field(label, value):
    val_str = str(value) if value is not None else f"{YELLOW}N/A{RESET}"
    print(f"{BOLD}{label:25}:{RESET} {val_str}")

def view_user_data(identity, force_tid=False):
    get_db, UserIdentity, FarmerIdentity, CoffeeBatch, VerifiableCredential, Organization, FarmerCooperative = get_db_and_models()
    
    with get_db() as db:
        # 1. Find UserIdentity
        user = None
        if force_tid or (isinstance(identity, str) and len(identity) > 5):
            user = db.query(UserIdentity).filter_by(telegram_user_id=str(identity)).first()
        
        if not user:
            try:
                user_id = int(identity)
                user = db.query(UserIdentity).filter_by(id=user_id).first()
            except ValueError:
                pass
        
        if not user:
            print(f"{RED}{BOLD}ERROR: User with identity '{identity}' not found.{RESET}")
            return

        # 2. Identity Profile
        print_section("IDENTITY PROFILE")
        print_field("Database ID", user.id)
        print_field("Telegram ID", user.telegram_user_id)
        print_field("Name", f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip())
        print_field("Username", user.telegram_username)
        print_field("Role", user.role)
        print_field("DID", user.did)
        print_field("GLN", user.gln)
        print_field("Phone", user.phone_number)
        print_field("Language", user.preferred_language)
        print_field("PIN Set", "Yes" if user.pin_hash else "No")
        print_field("Approved", user.is_approved)

        # 3. Organization Memberships
        print_section("ORGANIZATIONS & COOPERATIVES")
        if user.organization:
            print_field("Primary Org", f"{user.organization.name} (ID: {user.organization.id})")
        
        coops = db.query(FarmerCooperative).filter_by(farmer_id=user.id).all()
        if coops:
            for c in coops:
                coop_name = c.cooperative.name if c.cooperative else "Unknown"
                print_field("Cooperative Member", f"{coop_name} (Status: {c.status or 'Active'})")
        elif not user.organization:
            print(f"{YELLOW}No memberships found.{RESET}")

        # 4. Farmer Registration (Form Data)
        print_section("FARM REGISTRATION (FORM DATA)")
        farmer = db.query(FarmerIdentity).filter_by(did=user.did).first()
        if farmer:
            print_field("Farmer ID", farmer.farmer_id)
            print_field("Registered Name", farmer.name)
            print_field("Location Info", farmer.location)
            print_field("Farm Region", farmer.region)
            print_field("Country", farmer.country_code)
            print_field("GPS Coordinates", f"{farmer.latitude}, {farmer.longitude}" if farmer.latitude else None)
            print_field("Farm Size (ha)", farmer.farm_size_hectares)
            print_field("Certification", farmer.certification_status)
            print_field("GPS Verified", farmer.gps_verified_at)
        else:
            print(f"{YELLOW}No FarmerIdentity found for this user DID.{RESET}")

        # 5. Compliance Status
        if farmer:
            print_section("EUDR COMPLIANCE STATUS")
            print_field("Deforestation Risk", farmer.deforestation_risk)
            print_field("Compliant", farmer.deforestation_compliant)
            print_field("Check Timestamp", farmer.deforestation_checked_at)
            print_field("Data Source", farmer.deforestation_data_source)
            print_field("Confidence", farmer.deforestation_confidence)

        # 6. Inventory & Activity
        print_section("INVENTORY & ACTIVITY")
        batch_count = db.query(CoffeeBatch).filter_by(created_by_user_id=user.id).count()
        print_field("Total Batches", batch_count)
        
        recent_batches = db.query(CoffeeBatch).filter_by(created_by_user_id=user.id).order_by(CoffeeBatch.created_at.desc()).limit(5).all()
        if recent_batches:
            print(f"\n{BOLD}Recent Batches:{RESET}")
            for b in recent_batches:
                print(f" - {b.batch_id} ({b.quantity_kg}kg, {b.status})")

        # 7. Verifiable Credentials
        print_section("VERIFIABLE CREDENTIALS")
        if farmer:
            creds = farmer.credentials
            if creds:
                for c in creds:
                    print(f" - [{c.credential_type}] ID: {c.credential_id[:16]}... (Issued: {c.created_at.date()})")
            else:
                print(f"{YELLOW}No credentials found.{RESET}")
        else:
            print(f"{YELLOW}No farmer profile to link credentials.{RESET}")

    print(f"\n{BOLD}{BLUE}=== End of Report ==={RESET}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View all data associated with a user")
    parser.add_argument("identity", help="Database ID or Telegram User ID")
    parser.add_argument("--tid", action="store_true", help="Force interpretation as Telegram User ID")
    args = parser.parse_args()
    
    view_user_data(args.identity, force_tid=args.tid)
