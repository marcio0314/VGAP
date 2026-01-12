"""
VGAP Maintenance API Routes

Provides cleanup operations for platform maintenance.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from vgap.services.maintenance import dry_run_cleanup, execute_cleanup

router = APIRouter()


class CleanupRequest(BaseModel):
    """Request to execute cleanup."""
    confirm: bool = False


class CleanupItemResponse(BaseModel):
    """Single item that can/will be cleaned."""
    path: str
    type: str
    size: int
    size_human: str
    description: str


class DryRunResponse(BaseModel):
    """Response from dry run cleanup."""
    items: list[CleanupItemResponse]
    total_size: int
    total_size_human: str
    protected: list[str]
    timestamp: str


class CleanupResponse(BaseModel):
    """Response from actual cleanup."""
    success: bool
    deleted: list[str]
    space_freed: int
    space_freed_human: str
    errors: list[str]
    log_path: str
    timestamp: str


@router.get("/cleanup/preview", response_model=DryRunResponse)
async def preview_cleanup():
    """
    Preview what would be cleaned.
    
    Returns a list of files/directories that would be removed,
    their sizes, and what is protected.
    
    Does NOT modify any files.
    """
    result = dry_run_cleanup()
    return DryRunResponse(
        items=[CleanupItemResponse(**item) for item in result["items"]],
        total_size=result["total_size"],
        total_size_human=result["total_size_human"],
        protected=result["protected"],
        timestamp=result["timestamp"],
    )


@router.post("/cleanup/execute", response_model=CleanupResponse)
async def execute_cleanup_endpoint(request: CleanupRequest):
    """
    Execute cleanup of non-critical data.
    
    Requires confirm=True to actually delete.
    Logs all actions to cleanup.log for audit.
    
    Cleans:
    - Temporary processing files
    - Previous analysis results (can be regenerated)
    - Uploaded input files
    
    NEVER touches:
    - Source code
    - Reference databases
    - Configuration files
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Cleanup requires confirmation. Set confirm=true to proceed."
        )
    
    result = execute_cleanup(confirm=True)
    
    return CleanupResponse(
        success=result["success"],
        deleted=result["deleted"],
        space_freed=result["space_freed"],
        space_freed_human=result.get("space_freed_human", "0 B"),
        errors=result.get("errors", []),
        log_path=result.get("log_path", ""),
        timestamp=result["timestamp"],
    )
