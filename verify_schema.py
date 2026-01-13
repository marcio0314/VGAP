
from vgap.api.schemas import DatabaseInfo
from pydantic import ValidationError
import sys

try:
    print("Testing DatabaseInfo Schema...")
    # Test case: Uninstalled DB (path=None, status field present)
    db = DatabaseInfo(
        name="Flu-A",
        version=None,
        checksum=None,
        updated_at=None,
        updated_by=None,
        path=None,
        status="not_installed"
    )
    print("SUCCESS: DatabaseInfo accepted None path and status field.")
    print(f"Serialized: {db.model_dump_json()}")
except ValidationError as e:
    print("FAIL: Validation Error")
    print(e)
    sys.exit(1)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
