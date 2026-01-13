
import asyncio
import sys
import os
import json
from uuid import uuid4
from datetime import datetime

# Setup paths
sys.path.append("/app")

# Mock DB Session
class MockSession:
    async def execute(self, query):
        class MockResult:
            def scalars(self):
                class MockScalars:
                    def all(self):
                        return [] # Simulate empty DB or populated DB
                return MockScalars()
        return MockResult()
    
    def add(self, obj):
        print(f"Mock DB Add: {obj.name}")
        
    async def commit(self):
        print("Mock DB Commit")

async def diagnose():
    print("\n=== DIAGNOSTIC START ===")
    
    # 1. Check ReferenceManager contents
    try:
        from vgap.services.reference_manager import ReferenceManager, REFERENCE_SOURCES
        print(f"REFERENCE_SOURCES keys: {list(REFERENCE_SOURCES.keys())}")
        
        manager = ReferenceManager()
        inventory = manager.get_inventory()
        print("\n[ReferenceManager Inventory]")
        print(json.dumps(inventory, indent=2))
        
        if "influenza-a" not in inventory["references"]:
            print("CRITICAL: Influenza-A missing from inventory!")
        else:
            print("OK: Influenza-A present in inventory.")
            
    except Exception as e:
        print(f"CRITICAL ERROR in ReferenceManager: {e}")
        import traceback
        traceback.print_exc()

    # 2. Check Admin Route Logic (Simulated)
    print("\n[Admin Route Logic Check]")
    try:
        from vgap.api.routes.admin import list_databases
        # We can't easily call the async route without a real DB session, 
        # but we can check the file content on disk to ensure the patch is there.
        
        with open("/app/vgap/api/routes/admin.py", "r") as f:
            content = f.read()
            if "mix inventory" in content.lower() or "always fetch inventory" in content.lower():
                print("OK: Patch seems to be present in admin.py")
            else:
                print("CRITICAL: Patch markers NOT FOUND in admin.py")
                
    except Exception as e:
         print(f"Error checking admin.py: {e}")

    print("=== DIAGNOSTIC END ===\n")

if __name__ == "__main__":
    asyncio.run(diagnose())
