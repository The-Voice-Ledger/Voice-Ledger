"""
Migrate existing JSON data to Neon database
"""

import json
from pathlib import Path
from database.models import init_database, SessionLocal
from database.crud import create_batch, create_event, create_farmer
from datetime import datetime
from gs1.identifiers import gtin as generate_gtin

# Counter for generating unique GTINs
gtin_counter = 1000

def migrate_digital_twin():
    """Migrate twin/digital_twin.json to Neon."""
    
    print("="*60)
    print("Migrating Voice Ledger data to Neon database")
    print("="*60)
    
    # Ensure tables exist
    print("\n1. Checking database schema...")
    init_database()
    
    # Load existing twin data
    twin_file = Path("twin/digital_twin.json")
    if not twin_file.exists():
        print("\n✗ No digital_twin.json found.")
        print("  This is fine - starting with clean database.")
        return
    
    try:
        twin_data = json.loads(twin_file.read_text())
    except json.JSONDecodeError:
        print("\n✗ Invalid JSON in digital_twin.json")
        return
    
    db = SessionLocal()
    
    try:
        batches = twin_data.get("batches", {})
        print(f"\n2. Found {len(batches)} batches to migrate")
        
        migrated_count = 0
        global gtin_counter
        
        for batch_id, batch_data in batches.items():
            # Start fresh session for each batch to avoid rollback cascade
            db.rollback()
            
            print(f"\n   Migrating batch: {batch_id}")
            
            # Generate unique GTIN using GS1 standard
            if "gtin" in batch_data:
                gtin = batch_data["gtin"]
            else:
                gtin = generate_gtin(str(gtin_counter))
                gtin_counter += 1
            
            # Create batch record
            try:
                batch_record = create_batch(db, {
                    "batch_id": batch_id,
                    "gtin": gtin,
                    "batch_number": batch_data.get("batch_number", batch_id.split("-")[-1]),
                    "quantity_kg": float(batch_data.get("quantity_kg", 0)),
                    "origin": batch_data.get("origin", "Ethiopia"),
                    "variety": batch_data.get("variety", "Arabica"),
                    "harvest_date": datetime.fromisoformat(batch_data["harvest_date"]) if "harvest_date" in batch_data else None,
                    "processing_method": batch_data.get("processing_method"),
                    "quality_grade": batch_data.get("quality_grade"),
                    "farmer_id": None  # TODO: Link to farmer if exists
                })
                print(f"   ✓ Created batch {batch_id} (DB ID: {batch_record.id})")
                
                # Migrate events
                events = batch_data.get("events", [])
                for event in events:
                    event_time_str = event.get("event_time") or event.get("eventTime")
                    if event_time_str:
                        try:
                            event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
                        except:
                            event_time = datetime.utcnow()
                    else:
                        event_time = datetime.utcnow()
                    
                    create_event(db, {
                        "event_hash": event.get("hash", event.get("event_hash", f"hash_{batch_id}_{len(events)}")),
                        "event_type": event.get("type", "ObjectEvent"),
                        "canonical_nquads": event.get("canonical", ""),
                        "event_json": event,
                        "blockchain_tx_hash": event.get("tx_hash") or event.get("blockchain_tx_hash"),
                        "event_time": event_time,
                        "biz_step": event.get("biz_step", event.get("bizStep", "harvesting")),
                        "biz_location": event.get("biz_location"),
                        "batch_id": batch_record.id,
                        "submitter_id": None  # TODO: Link to farmer
                    })
                
                print(f"   ✓ Migrated {len(events)} events for {batch_id}")
                migrated_count += 1
                
            except Exception as e:
                print(f"   ✗ Error migrating {batch_id}: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"✓ Migration complete!")
        print(f"  - Migrated {migrated_count} batches")
        print(f"  - Data now stored in Neon PostgreSQL")
        print(f"{'='*60}")
        
        # Backup original file
        backup_file = Path("twin/digital_twin.json.backup")
        if not backup_file.exists():
            twin_file.rename(backup_file)
            print(f"\n✓ Original file backed up to {backup_file}")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_digital_twin()
