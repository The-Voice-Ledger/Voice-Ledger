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
    # Only import heavy database/blockchain modules inside here
    from database.connection import get_db
    from database.models import CoffeeBatch, FarmerIdentity, EPCISEvent, VerifiableCredential, UserIdentity
    return get_db, CoffeeBatch, FarmerIdentity, EPCISEvent, VerifiableCredential, UserIdentity

def print_check(label, status, message=""):
    color = GREEN if status == "PASS" else (YELLOW if status == "WARN" else RED)
    icon = "✓" if status == "PASS" else ("!" if status == "WARN" else "✗")
    print(f"{color}{BOLD}[{icon}] {label:25}{RESET} {message}")

def fix_batch_data(db, batch, FarmerIdentity, CoffeeBatch):
    """
    Attempt to automatically fix missing links and data for a batch.
    """
    modified = False
    print(f"\n{BOLD}{BLUE}--- Attempting Auto-Fix ---{RESET}")

    # 1. Fix Farmer Link
    if not batch.farmer_id:
        from database.models import UserIdentity
        user = db.query(UserIdentity).filter_by(id=batch.created_by_user_id).first()
        if user and user.did:
            farmer = db.query(FarmerIdentity).filter_by(did=user.did).first()
            if farmer:
                batch.farmer_id = farmer.id
                print_check("Auto-Link Farmer", "PASS", f"Linked to {farmer.name}")
                modified = True
            else:
                print_check("Auto-Link Farmer", "FAIL", "No FarmerIdentity found for user DID")
        else:
            print_check("Auto-Link Farmer", "FAIL", "Creator user or DID not found")
    
    # 2. Fix Farmer Profile Data (Region/Country)
    if batch.farmer:
        f_modified = False
        if not batch.farmer.region or batch.farmer.region.lower() == "none" or batch.farmer.region == "":
            # Infer region from batch_id (e.g., SIDAMA_WASHED...)
            parts = batch.batch_id.split('_')
            inferred_region = parts[0].capitalize() if parts else None
            if inferred_region:
                batch.farmer.region = inferred_region
                print_check("Auto-Fix Farmer Region", "PASS", f"Set to {inferred_region}")
                f_modified = True
        
        if not batch.farmer.country_code:
            batch.farmer.country_code = "ET" 
            print_check("Auto-Fix Farmer Country", "PASS", "Set to ET")
            f_modified = True
            
        if f_modified:
            modified = True

    # 3. Fix Origin from Farmer Profile
    if not batch.origin or batch.origin.lower() == "unknown":
        db.flush() 
        if batch.farmer and batch.farmer.region:
            new_origin = f"{batch.farmer.region}, {batch.farmer.country_code or 'ET'}"
            batch.origin = new_origin
            print_check("Auto-Fill Origin", "PASS", f"Set to {new_origin}")
            modified = True
        else:
            print_check("Auto-Fill Origin", "WARN", "Cannot fill origin without farmer region")

    if modified:
        db.commit()
        print(f"{GREEN}{BOLD}SUCCESS: Batch and Farmer record updated.{RESET}")
    else:
        print(f"{YELLOW}No automatic fixes could be applied.{RESET}")
    
    return modified

def check_batch_dpp(batch_id: str, auto_fix: bool = False):
    """
    Diagnose a coffee batch and report missing data for DPP generation.
    """
    get_db, CoffeeBatch, FarmerIdentity, EPCISEvent, VerifiableCredential, UserIdentity = get_db_and_models()
    
    print(f"\n{BOLD}{BLUE}=== DPP Diagnostic Tool: {batch_id} ==={RESET}\n")

    with get_db() as db:
        # 1. Basic Batch Check
        batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
        if not batch:
            print(f"{RED}{BOLD}ERROR: Batch '{batch_id}' not found in database.{RESET}")
            return

        if auto_fix:
            fix_batch_data(db, batch, FarmerIdentity, CoffeeBatch)
            db.refresh(batch)

        print(f"\n{BOLD}1. CORE BATCH DATA{RESET}")
        print_check("Batch ID", "PASS", batch.batch_id)
        print_check("GTIN", "PASS" if batch.gtin else "FAIL", batch.gtin or "Missing")
        print_check("Quantity", "PASS" if batch.quantity_kg > 0 else "FAIL", f"{batch.quantity_kg}kg")
        print_check("Status", "PASS" if batch.status == 'VERIFIED' else "WARN", batch.status)
        print_check("Variety", "PASS" if batch.variety else "WARN", batch.variety or "Not set")
        
        # 2. Farmer Association
        print(f"\n{BOLD}2. FARMER IDENTITY{RESET}")
        farmer = batch.farmer
        if farmer:
            print_check("Linked Farmer", "PASS", f"{farmer.name} (ID: {farmer.farmer_id})")
            print_check("Farmer DID", "PASS", farmer.did)
            print_check("GLN", "PASS" if farmer.gln else "WARN", farmer.gln or "Missing (Global Location Number)")
            print_check("Region/Country", "PASS" if farmer.region and farmer.country_code else "FAIL", f"{farmer.region}, {farmer.country_code}")
        else:
            print_check("Linked Farmer", "FAIL", "No farmer associated with this batch!")
            print(f"   {YELLOW}Hint: Use --fix flag to auto-link if creator has a farmer profile.{RESET}")

        # 3. EUDR Geolocation & Compliance
        print(f"\n{BOLD}3. EUDR & COMPLIANCE{RESET}")
        if farmer:
            has_gps = farmer.latitude is not None and farmer.longitude is not None
            print_check("GPS Coordinates", "PASS" if has_gps else "FAIL", f"{farmer.latitude}, {farmer.longitude}" if has_gps else "Missing (Required for EUDR)")
            
            is_gps_verified = farmer.gps_verified_at is not None
            print_check("GPS Verification", "PASS" if is_gps_verified else "WARN", f"Verified at {farmer.gps_verified_at}" if is_gps_verified else "Farm photo GPS check missing")
            
            print_check("Deforestation Check", "PASS" if farmer.deforestation_compliant else "FAIL", f"{farmer.deforestation_risk} risk" if farmer.deforestation_checked_at else "Not yet performed")
        else:
            print_check("Compliance Data", "FAIL", "Cannot verify compliance without farmer record.")

        # 4. Supply Chain Events (EPCIS)
        print(f"\n{BOLD}4. TRACEABILITY EVENTS (EPCIS){RESET}")
        events = batch.events
        has_commission = any(e.biz_step == 'commissioning' for e in events)
        has_verification = any(e.biz_step == 'verification' for e in events)
        
        print_check("Commissioning Event", "PASS" if has_commission else "FAIL", "Required for provenance")
        print_check("Verification Event", "PASS" if has_verification else "WARN", "Required for 'Verified' status display")
        
        # 5. Credentials
        print(f"\n{BOLD}5. VERIFIABLE CREDENTIALS{RESET}")
        if farmer:
            creds = farmer.credentials
            cert_count = len([c for c in creds if "certification" in c.credential_type.lower()])
            dd_count = len([c for c in creds if "duediligence" in c.credential_type.lower()])
            
            print_check("Certifications", "PASS" if cert_count > 0 else "WARN", f"{cert_count} found")
            print_check("Due Diligence", "PASS" if dd_count > 0 else "FAIL", f"{dd_count} found (Required for EUDR Gold status)")
        else:
            print_check("Credentials", "FAIL", "No farmer linked to load credentials.")

    print(f"\n{BOLD}{BLUE}--- End of Diagnosis ---{RESET}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DPP Data Diagnostic & Fix Tool")
    parser.add_argument("batch_id", help="The Coffee Batch ID to check (e.g. SIDAMA_WASHED_ARABICA_...)")
    parser.add_argument("--fix", action="store_true", help="Attempt to automatically fix missing data and link farmer")
    args = parser.parse_args()
    
    check_batch_dpp(args.batch_id, auto_fix=args.fix)
