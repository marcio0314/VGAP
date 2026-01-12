"""
VGAP Maintenance Module

Provides safe cleanup operations for the platform.
Uses explicit allowlists - never wildcard deletes.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from vgap.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


# Explicit allowlist of directories that can be cleaned
# NEVER add source code, references, or configuration to this list
CLEANABLE_PATHS = {
    "temp_files": {
        "path": "temp",
        "description": "Temporary processing files",
        "safe": True,
    },
    "old_logs": {
        "path": "logs",
        "description": "Application logs (older than 7 days)",
        "safe": True,
    },
    "cache_files": {
        "path": ".cache",
        "description": "Python and tool caches",
        "safe": True,
    },
    "pycache": {
        "path": "__pycache__",
        "description": "Python bytecode cache",
        "safe": True,
        "recursive": True,
    },
}

# Paths that are NEVER touched
PROTECTED_PATHS = [
    "vgap",           # Source code
    "frontend/src",   # Frontend source
    "references",     # Scientific reference databases
    "docker",         # Docker configuration
    ".env",           # Environment config
    "pyproject.toml", # Project config
    "README.md",      # Documentation
]


def get_data_dir() -> Path:
    """Get the data directory from settings."""
    return Path(os.environ.get("DATA_DIR", "/data"))


def calculate_directory_size(path: Path) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    if path.exists() and path.is_dir():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def dry_run_cleanup() -> dict[str, Any]:
    """
    Perform a dry run of cleanup - shows what would be deleted.
    Does NOT modify any files.
    
    Returns dict with:
        - items: list of items that would be cleaned
        - total_size: total bytes to be freed
        - protected: list of protected paths (not touched)
    """
    data_dir = get_data_dir()
    results = {
        "items": [],
        "total_size": 0,
        "total_size_human": "0 B",
        "protected": PROTECTED_PATHS,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Check temp directory
    temp_dir = data_dir / "temp"
    if temp_dir.exists():
        size = calculate_directory_size(temp_dir)
        results["items"].append({
            "path": str(temp_dir),
            "type": "directory",
            "size": size,
            "size_human": format_size(size),
            "description": "Temporary processing files",
        })
        results["total_size"] += size
    
    # Check results directory for old/incomplete runs
    results_dir = data_dir / "results"
    if results_dir.exists():
        size = calculate_directory_size(results_dir)
        results["items"].append({
            "path": str(results_dir),
            "type": "directory",
            "size": size,
            "size_human": format_size(size),
            "description": "Previous analysis results (regenerable)",
        })
        results["total_size"] += size
    
    # Check uploads directory
    uploads_dir = data_dir / "uploads"
    if uploads_dir.exists():
        size = calculate_directory_size(uploads_dir)
        results["items"].append({
            "path": str(uploads_dir),
            "type": "directory",
            "size": size,
            "size_human": format_size(size),
            "description": "Uploaded input files",
        })
        results["total_size"] += size
    
    results["total_size_human"] = format_size(results["total_size"])
    
    return results


def execute_cleanup(confirm: bool = False) -> dict[str, Any]:
    """
    Execute cleanup of non-critical data.
    
    Args:
        confirm: Must be True to actually delete. Safety check.
    
    Returns dict with:
        - success: bool
        - deleted: list of deleted items
        - space_freed: bytes freed
        - errors: list of any errors
        - log_path: path to cleanup log
    """
    if not confirm:
        return {
            "success": False,
            "message": "Cleanup not confirmed. Set confirm=True to proceed.",
            "deleted": [],
            "space_freed": 0,
        }
    
    data_dir = get_data_dir()
    results = {
        "success": True,
        "deleted": [],
        "space_freed": 0,
        "errors": [],
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Log file for audit
    log_path = data_dir / "cleanup.log"
    
    def log_action(action: str, path: str, size: int = 0):
        """Log cleanup action to file."""
        timestamp = datetime.utcnow().isoformat()
        with open(log_path, "a") as f:
            f.write(f"{timestamp} | {action} | {path} | {format_size(size)}\n")
        logger.info("Cleanup action", action=action, path=path, size=size)
    
    log_action("CLEANUP_START", str(data_dir))
    
    # Clean temp directory
    temp_dir = data_dir / "temp"
    if temp_dir.exists():
        try:
            size = calculate_directory_size(temp_dir)
            shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            results["deleted"].append(str(temp_dir))
            results["space_freed"] += size
            log_action("DELETED", str(temp_dir), size)
        except Exception as e:
            results["errors"].append(f"Failed to clean temp: {e}")
            log_action("ERROR", str(temp_dir))
    
    # Clean results directory
    results_dir = data_dir / "results"
    if results_dir.exists():
        try:
            size = calculate_directory_size(results_dir)
            shutil.rmtree(results_dir)
            results_dir.mkdir(parents=True, exist_ok=True)
            results["deleted"].append(str(results_dir))
            results["space_freed"] += size
            log_action("DELETED", str(results_dir), size)
        except Exception as e:
            results["errors"].append(f"Failed to clean results: {e}")
            log_action("ERROR", str(results_dir))
    
    # Clean uploads directory
    uploads_dir = data_dir / "uploads"
    if uploads_dir.exists():
        try:
            size = calculate_directory_size(uploads_dir)
            shutil.rmtree(uploads_dir)
            uploads_dir.mkdir(parents=True, exist_ok=True)
            results["deleted"].append(str(uploads_dir))
            results["space_freed"] += size
            log_action("DELETED", str(uploads_dir), size)
        except Exception as e:
            results["errors"].append(f"Failed to clean uploads: {e}")
            log_action("ERROR", str(uploads_dir))
    
    results["space_freed_human"] = format_size(results["space_freed"])
    results["log_path"] = str(log_path)
    
    if results["errors"]:
        results["success"] = False
    
    log_action("CLEANUP_END", f"Freed {results['space_freed_human']}")
    
    return results
