"""
Migration: add uat_issues table

Usage:
    python database/migrations/add_uat_issues.py

Safe to run multiple times (uses CREATE TABLE IF NOT EXISTS / checkfirst=True).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database.models import UATIssue, engine

def run():
    print("Creating uat_issues table if it does not exist...")
    UATIssue.__table__.create(bind=engine, checkfirst=True)
    print("Done.")

if __name__ == '__main__':
    run()
