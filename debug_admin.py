
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from vgap.services.reference_manager import ReferenceManager, REFERENCE_SOURCES
from vgap.api.routes.admin import list_databases
from vgap.config import settings

def test_inventory_logic():
    print("--- 1. Testing ReferenceManager Inventory ---")
    manager = ReferenceManager()
    inventory = manager.get_inventory()
    
    print(f"Sources in Code: {list(REFERENCE_SOURCES.keys())}")
    print(f"Inventory keys: {list(inventory['references'].keys())}")
    
    found_missing = False
    for ref in REFERENCE_SOURCES:
        if ref not in inventory['references']:
            print(f"ERROR: {ref} missing from inventory!")
            found_missing = True
        else:
            status = inventory['references'][ref]['status']
            print(f"  {ref}: {status}")
            
    print("\n--- 2. Testing Admin Merge Logic (Simulation) ---")
    # Simulate what I wrote in administrative.py
    
    response = []
    # Mocking db_records as empty dict (simulating fresh install or just checking merge)
    db_records = {} 
    
    count = 0
    for ref_id, data in inventory.get("references", {}).items():
        print(f"  Processing {ref_id} ({data['name']})...")
        response.append({
            "name": data["name"],
            "status": data["status"]
        })
        count += 1
        
    print(f"Total items in simulated response: {count}")
    
    if count < len(REFERENCE_SOURCES):
        print("ERROR: Response logic is dropping items!")
    else:
        print("SUCCESS: Logic seems sound locally.")

if __name__ == "__main__":
    test_inventory_logic()
