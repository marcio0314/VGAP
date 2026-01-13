from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List
from pydantic import BaseModel

from vgap.services.cleanup_manager import CleanupManager
from vgap.tasks.maintenance import prune_docker_resources, scan_docker_usage

router = APIRouter(tags=["maintenance"])

class CleanupPolicy(BaseModel):
    delete_temp_files: bool = True
    delete_orphaned_uploads: bool = False # Safer default
    retention_days_runs: int = 5
    retention_days_reports: int = 14
    prune_docker_images: bool = False
    prune_docker_volumes: bool = False

@router.get("/usage")
async def get_disk_usage() -> Dict[str, Any]:
    """
    Get current disk usage statistics (Files + Docker).
    """
    manager = CleanupManager()
    local_stats = manager.scan_usage()
    
    # Attempt to get docker stats
    docker_stats = {"status": "unavailable"}
    try:
        # We use a short timeout to not block too long
        task = scan_docker_usage.apply_async()
        # Wait up to 3 seconds
        docker_stats = task.get(timeout=3.0)
    except Exception as e:
        docker_stats["error"] = str(e)

    return {
        "local": local_stats,
        "docker": docker_stats
    }

@router.post("/cleanup/preview")
async def preview_cleanup(policy: CleanupPolicy) -> Dict[str, Any]:
    """
    Preview what would be deleted based on the policy.
    Note: Docker prune does not support granular preview easily, so it just warns.
    """
    manager = CleanupManager()
    preview = manager.preview_cleanup(policy.model_dump())
    
    if policy.prune_docker_images:
        preview["docker_warning"] = "Docker images and build cache will be pruned."
    
    return preview

@router.post("/cleanup/execute")
async def execute_cleanup(
    policy: CleanupPolicy, 
    background_tasks: BackgroundTasks,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Execute cleanup. Requires confirm=True.
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")

    manager = CleanupManager()
    
    # 1. Generate list (re-scan to be safe)
    preview = manager.preview_cleanup(policy.model_dump())
    files_to_delete = preview.get("files_to_delete", [])
    
    # 2. Execute Local Cleanup immediately (it's fast enough usually, or background it?)
    # Let's run it synchronously to return immediate results for files
    local_result = manager.execute_cleanup(files_to_delete)
    
    # 3. Trigger Docker Cleanup in Background
    docker_task_id = None
    if policy.prune_docker_images:
        task = prune_docker_resources.delay(deep=policy.prune_docker_volumes)
        docker_task_id = task.id

    return {
        "local_cleanup": local_result,
        "docker_task_id": docker_task_id,
        "message": "Cleanup initiated"
    }
