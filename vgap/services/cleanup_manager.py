import logging
import shutil
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from vgap.config import settings

logger = logging.getLogger(__name__)

class CleanupManager:
    """
    Manages disk usage audit and cleanup operations.
    Enforces strict safety zones and allowlists.
    """

    # Protected paths that must NEVER be deleted
    SAFETY_ZONES = [
        "/app/vgap",
        "/app/frontend",
        "/app/docker",
        "/boot",
        "/etc",
        "/usr",
        "/bin",
        "/sbin",
        "/lib",
        "/proc",
        "/sys",
        "/dev",
        str(settings.storage.references_dir), # Protect references by default
    ]

    # Allowed targets for cleanup (must start with one of these)
    ALLOWLIST_PREFIXES = [
        str(settings.storage.temp_dir),
        str(settings.storage.upload_dir),
        str(settings.storage.results_dir),
        str(settings.storage.data_dir / "cache"),
        str(settings.storage.data_dir / "reports"), # If distinct from results
    ]

    def __init__(self):
        self.data_dir = settings.storage.data_dir

    def scan_usage(self) -> Dict[str, Any]:
        """
        Scans disk usage of configured data directories.
        Returns a dictionary with usage stats per category.
        """
        stats = {
            "temp": self._get_dir_size(settings.storage.temp_dir),
            "uploads": self._get_dir_size(settings.storage.upload_dir),
            "results": self._get_dir_size(settings.storage.results_dir),
            "references": self._get_dir_size(settings.storage.references_dir),
            "total_free": shutil.disk_usage(self.data_dir).free,
            "total_used": shutil.disk_usage(self.data_dir).used,
            "total_capacity": shutil.disk_usage(self.data_dir).total,
            "timestamp": datetime.utcnow().isoformat()
        }
        return stats

    def preview_cleanup(self, retention_policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a preview of files to be deleted based on retention policy.
        retention_policy keys:
            - max_run_age_days (int)
            - max_report_age_days (int)
            - delete_temp_files (bool)
            - delete_orphaned_uploads (bool)
        """
        preview = {
            "files_to_delete": [],
            "total_size_reclaimable": 0,
            "policy_used": retention_policy
        }

        # 1. Temp files
        if retention_policy.get("delete_temp_files", False):
            temp_files = self._scan_candidates(
                settings.storage.temp_dir, 
                min_age_hours=1
            )
            preview["files_to_delete"].extend(temp_files)

        # 2. Orphans
        if retention_policy.get("delete_orphaned_uploads", False):
            # TODO: Implement connection to DB to check for orphaned uploads
            # For now, we'll skip DB check and rely on age
            orphaned = self._scan_candidates(
                settings.storage.upload_dir,
                min_age_hours=24
            )
            preview["files_to_delete"].extend(orphaned)
        
        # Calculate total
        preview["total_size_reclaimable"] = sum(item["size"] for item in preview["files_to_delete"])
        
        return preview

    def execute_cleanup(self, files_to_delete: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executes cleanup for a specific list of files.
        """
        results = {
            "deleted_count": 0,
            "reclaimed_bytes": 0,
            "errors": []
        }

        for file_info in files_to_delete:
            path = Path(file_info["path"])
            
            # Safety Check 1: Is it in Allowlist?
            if not self._is_path_allowed(path):
                results["errors"].append(f"SKIPPED (Not allowed): {path}")
                continue

            # Safety Check 2: Is it in Safety Zone?
            if self._is_path_protected(path):
                results["errors"].append(f"SKIPPED (Protected): {path}")
                continue

            # Execute Delete
            try:
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
                
                results["deleted_count"] += 1
                results["reclaimed_bytes"] += file_info["size"]
                logger.info(f"Deleted: {path}")

            except Exception as e:
                results["errors"].append(f"ERROR {path}: {str(e)}")
                logger.error(f"Failed to delete {path}: {e}")

        return results

    def _get_dir_size(self, path: Path) -> Dict[str, Any]:
        """Calculates total size and file count of a directory."""
        total_size = 0
        file_count = 0
        if path.exists():
            for p in path.rglob('*'):
                if p.is_file():
                    total_size += p.stat().st_size
                    file_count += 1
        return {
            "path": str(path),
            "size_bytes": total_size,
            "file_count": file_count
        }

    def _scan_candidates(self, root: Path, min_age_hours: int = 0) -> List[Dict[str, Any]]:
        """Finds files in root older than min_age_hours."""
        candidates = []
        if not root.exists():
            return candidates

        threshold = time.time() - (min_age_hours * 3600)
        
        try:
            for p in root.rglob('*'):
                if p.is_file():
                    stat = p.stat()
                    if stat.st_mtime < threshold:
                        candidates.append({
                            "path": str(p),
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "reason": f"Older than {min_age_hours}h"
                        })
        except Exception as e:
            logger.error(f"Error scanning {root}: {e}")
            
        return candidates

    def _is_path_allowed(self, path: Path) -> bool:
        """Checks if path starts with an allowed prefix."""
        s_path = str(path.resolve())
        return any(s_path.startswith(prefix) for prefix in self.ALLOWLIST_PREFIXES)

    def _is_path_protected(self, path: Path) -> bool:
        """Checks if path is within a safety zone."""
        s_path = str(path.resolve())
        return any(s_path.startswith(zone) for zone in self.SAFETY_ZONES)
