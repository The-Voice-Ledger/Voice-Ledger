#!/usr/bin/env python3
import sys
import os
import time
import argparse
from datetime import datetime
import logging

# Ensure UTF-8 output for Windows terminals (avoid UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ANSI Color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_db_and_models():
    from database.connection import get_db
    from database.models import CoffeeBatch, FarmerIdentity, UserIdentity, Organization
    return get_db, CoffeeBatch, FarmerIdentity, UserIdentity, Organization

def print_status(icon, message, color=GREEN):
    print(f"{color}{BOLD}[{icon}] {message}{RESET}")

def autopilot_process_batch(db, batch_id_or_obj, verifier_tid):
    """
    Diagnose, fix, and verify a batch in one go.
    """
    get_db, CoffeeBatch, FarmerIdentity, UserIdentity, Organization = get_db_and_models()
    
    # Resolve batch
    if isinstance(batch_id_or_obj, str):
        batch = db.query(CoffeeBatch).filter(
            (CoffeeBatch.batch_id == batch_id_or_obj) | (CoffeeBatch.batch_number == batch_id_or_obj)
        ).first()
    else:
        batch = batch_id_or_obj
        
    if not batch:
        print_status("✗", f"Batch {batch_id_or_obj} not found.", RED)
        return False

    print(f"\n{BOLD}{BLUE}>>> Processing Batch: {batch.batch_id}{RESET}")

    # PHASE 1: Auto-Fix (from check_batch_dpp logic)
    modified = False
    
    # 1.1 Link Farmer
    if not batch.farmer_id:
        user = db.query(UserIdentity).filter_by(id=batch.created_by_user_id).first()
        if user and user.did:
            farmer = db.query(FarmerIdentity).filter_by(did=user.did).first()
            if farmer:
                batch.farmer_id = farmer.id
                print_status("✓", f"Linked Farmer: {farmer.name}")
                modified = True
            else:
                print_status("!", "No Farmer profile found for creator DID.", YELLOW)
        else:
            print_status("!", "No creator identity found.", YELLOW)

    # 1.2 Fix Region/Country and Origin
    if batch.farmer:
        f_modified = False
        if not batch.farmer.region or batch.farmer.region.lower() == "none" or batch.farmer.region == "":
            parts = batch.batch_id.split('_')
            inferred_region = parts[0].capitalize() if parts else "Sidama"
            batch.farmer.region = inferred_region
            print_status("✓", f"Fixed Farmer Region: {inferred_region}")
            f_modified = True
        
        if not batch.farmer.country_code:
            batch.farmer.country_code = "ET"
            print_status("✓", "Fixed Farmer Country: ET")
            f_modified = True
            
        if f_modified:
            modified = True
            db.flush()

        if not batch.origin or batch.origin.lower() == "unknown":
            new_origin = f"{batch.farmer.region}, {batch.farmer.country_code or 'ET'}"
            batch.origin = new_origin
            print_status("✓", f"Auto-filled Batch Origin: {new_origin}")
            modified = True

    if modified:
        db.commit()
    
    # PHASE 2: Verification (from verify_batch logic)
    if batch.status == "VERIFIED":
        print_status("ℹ", f"Batch is already verified.", YELLOW)
    else:
        from verify_batch import verify_batch
        success = verify_batch(
            batch_id=batch.batch_id,
            verifier_telegram_id=verifier_tid,
            verified_quantity=batch.quantity_kg,
            notes="Auto-verified by Autopilot DPP Tool for Hackathon Demo."
        )
        if success:
            print_status("★", f"SUCCESS: Batch {batch.batch_id} is now LIVE and DPP is accessible!", GREEN)
            return True
        else:
            print_status("✗", f"Verification failed for {batch.batch_id}.", RED)
            return False
    
    return True

def watch_mode(verifier_tid, interval=5):
    get_db, CoffeeBatch, FarmerIdentity, UserIdentity, Organization = get_db_and_models()
    
    print(f"\n{BOLD}{BLUE}🛰  VOICE LEDGER AUTOPILOT WATCHER ACTIVE{RESET}")
    print(f"Monitoring for new batches... (Polling every {interval}s)")
    print(f"Verifier context: {verifier_tid}\n")
    
    try:
        while True:
            with get_db() as db:
                # Find batches awaiting verification
                pending = db.query(CoffeeBatch).filter(
                    (CoffeeBatch.status == 'PENDING_VERIFICATION') | (CoffeeBatch.status == None)
                ).all()
                
                if pending:
                    print(f"\n{BOLD}{YELLOW}Found {len(pending)} pending batch(es). Processing...{RESET}")
                    for batch in pending:
                        autopilot_process_batch(db, batch, verifier_tid)
                
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n{BOLD}{BLUE}Watcher stopped.{RESET}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autopilot DPP: Diagnose, Fix, and Verify Coffee Batches")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: process
    proc_parser = subparsers.add_parser("process", help="Process a specific batch")
    proc_parser.add_argument("batch_id", help="The batch_id to process")
    proc_parser.add_argument("--verifier", required=True, help="Telegram ID of the verifier")

    # Command: watch
    watch_parser = subparsers.add_parser("watch", help="Watch for new batches and process them automatically")
    watch_parser.add_argument("--verifier", required=True, help="Telegram ID to use for auto-verification")
    watch_parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds")

    args = parser.parse_args()

    if args.command == "process":
        get_db, CoffeeBatch, FarmerIdentity, UserIdentity, Organization = get_db_and_models()
        with get_db() as db:
            autopilot_process_batch(db, args.batch_id, args.verifier)
    elif args.command == "watch":
        watch_mode(args.verifier, args.interval)
    else:
        parser.print_help()
