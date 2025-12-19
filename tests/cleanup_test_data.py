"""
Clean up all test data from database before running tests.
"""

from database.connection import get_db
from database.models import FarmerIdentity, CoffeeBatch, EPCISEvent, AggregationRelationship

def cleanup_all_test_data():
    """Delete all test data from database"""
    with get_db() as db:
        # Find test farmers
        test_farmers = db.query(FarmerIdentity).filter(
            (FarmerIdentity.farmer_id.like('FARMER-TEST%')) | 
            (FarmerIdentity.farmer_id.like('FARMER-RECURSIVE%'))
        ).all()
        farmer_ids = [f.id for f in test_farmers]
        
        # Find test batches
        test_batches = db.query(CoffeeBatch).filter(
            (CoffeeBatch.batch_id.like('TEST%')) | 
            (CoffeeBatch.batch_id.like('RECURSIVE%'))
        ).all()
        batch_ids = [b.id for b in test_batches]
        
        # Delete in correct order
        if batch_ids:
            deleted_agg = db.query(AggregationRelationship).filter(
                (AggregationRelationship.parent_sscc.like('%TEST%')) | 
                (AggregationRelationship.parent_sscc.like('%RECURSIVE%')) |
                (AggregationRelationship.child_identifier.like('%TEST%')) |
                (AggregationRelationship.child_identifier.like('%RECURSIVE%'))
            ).delete(synchronize_session=False)
            print(f'Deleted {deleted_agg} aggregation relationships')
        
        if batch_ids:
            deleted_events = db.query(EPCISEvent).filter(EPCISEvent.batch_id.in_(batch_ids)).delete(synchronize_session=False)
            print(f'Deleted {deleted_events} events')
        
        if batch_ids:
            deleted_batches = db.query(CoffeeBatch).filter(CoffeeBatch.id.in_(batch_ids)).delete(synchronize_session=False)
            print(f'Deleted {deleted_batches} batches')
        
        if farmer_ids:
            deleted_farmers = db.query(FarmerIdentity).filter(FarmerIdentity.id.in_(farmer_ids)).delete(synchronize_session=False)
            print(f'Deleted {deleted_farmers} farmers')
        
        print('✅ Cleanup complete')

if __name__ == "__main__":
    cleanup_all_test_data()
