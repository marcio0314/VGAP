"""
VGAP Run Management Routes

Database-backed run creation, monitoring, and management.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from vgap.api.routes.auth import get_current_user, require_admin, require_analyst_or_admin
from vgap.api.schemas import (
    RunCreate, RunResponse, RunStatus as RunStatusSchema, RunListResponse,
    RunStartResponse, ValidationResultResponse, ProvenanceResponse,
    PipelineMode, RunDetailResponse,
)
from vgap.config import get_settings
from vgap.api.schemas.parameters import RunParameters
from vgap.models import User, Run, RunStatus
from vgap.services.database import get_session
from vgap.services.run_service import (
    create_run, add_sample_to_run, get_run_by_id, list_runs,
    update_run_status, cancel_run, start_run, get_run_samples,
    get_run_sample_count,
)
from vgap.services.upload import UploadService
from vgap.validators.preflight import PreflightValidator

router = APIRouter()
settings = get_settings()


def run_to_response(run: Run, sample_count: int = 0) -> RunResponse:
    """Convert Run model to response schema."""
    return RunResponse(
        id=run.id,
        run_code=run.run_code,
        name=run.name,
        description=run.description,
        status=run.status.value,
        mode=run.mode,
        primer_scheme=run.primer_scheme,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        sample_count=sample_count,
        progress=run.progress or 0,
        current_stage=run.current_stage,
        error_message=run.error_message,
    )


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_new_run(
    run_data: RunCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_analyst_or_admin),
):
    """
    Create a new analysis run.
    
    Creates a run record and associated samples. Files must be uploaded
    separately via the upload endpoint before starting the run.
    """
    # Validate mode-specific requirements
    if run_data.mode == PipelineMode.AMPLICON and not run_data.primer_scheme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Primer scheme required for amplicon mode"
        )
    
    # Create run
    run = await create_run(
        session=session,
        name=run_data.name,
        mode=run_data.mode.value,
        user_id=current_user.id,
        description=run_data.description,
        primer_scheme=run_data.primer_scheme,
        reference_id=run_data.reference_id,
        parameters=run_data.parameters,
        run_parameters=run_data.run_parameters,
        project_id=run_data.project_id,
    )
    
    # Handle file uploads
    upload_service = UploadService()
    if run_data.upload_session_id:
        try:
            await upload_service.promote_session_to_run(
                run_data.upload_session_id, str(run.id)
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
            
    # Add samples
    for sample_data in run_data.samples:
        # Get file paths from upload session
        r1_path = str(upload_service.get_file_path(
            str(run.id), sample_data.r1_filename
        ))
        r2_path = None
        if sample_data.r2_filename:
            r2_path = str(upload_service.get_file_path(
                str(run.id), sample_data.r2_filename
            ))
        
        await add_sample_to_run(
            session=session,
            run_id=run.id,
            sample_id=sample_data.metadata.sample_id,
            metadata=sample_data.metadata.model_dump(),
            r1_path=r1_path,
            r2_path=r2_path,
        )
    
    await session.commit()
    
    sample_count = len(run_data.samples)
    
    return run_to_response(run, sample_count)


@router.get("", response_model=RunListResponse)
async def list_all_runs(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    List runs visible to the current user.
    
    Analysts see only their runs. Admins see all runs.
    """
    # Filter by user unless admin
    user_id = None if current_user.role.value == "admin" else current_user.id
    
    # Parse status filter
    status_enum = None
    if status_filter:
        try:
            status_enum = RunStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    
    runs, total = await list_runs(
        session=session,
        user_id=user_id,
        status_filter=status_enum,
        skip=skip,
        limit=limit,
    )
    
    # Get sample counts
    items = []
    for run in runs:
        count = await get_run_sample_count(session, run.id)
        items.append(run_to_response(run, count))
    
    return RunListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run_details(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific run."""
    run = await get_run_by_id(session, run_id, include_samples=True)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    # Check access
    if current_user.role.value != "admin" and run.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    sample_count = await get_run_sample_count(session, run_id)
    
    # Calculate variant counts for response
    for sample in run.samples:
        sample.variant_count = len(sample.variants) if sample.variants else 0
    
    return RunDetailResponse(
        id=run.id,
        run_code=run.run_code,
        name=run.name,
        description=run.description,
        status=run.status.value,
        mode=run.mode,
        primer_scheme=run.primer_scheme,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        sample_count=sample_count,
        progress=run.progress or 0,
        current_stage=run.current_stage,
        error_message=run.error_message,
        parameters=run.parameters,
        samples=run.samples,
        provenance=run.provenance,
    )


@router.get("/{run_id}/status", response_model=RunStatusSchema)
async def get_run_status(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get current status of a run for polling."""
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    return RunStatusSchema(
        status=run.status.value,
        progress=run.progress or 0,
        current_stage=run.current_stage,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
    )


@router.post("/{run_id}/start", response_model=RunStartResponse)
async def start_run_processing(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_analyst_or_admin),
):
    """
    Start processing a pending run.
    
    Validates inputs and queues the run for Celery processing.
    """
    run = await get_run_by_id(session, run_id, include_samples=True)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    if run.status != RunStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run cannot be started from status: {run.status.value}"
        )
    
    # Pre-flight validation
    samples = await get_run_samples(session, run_id)
    if not samples:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run has no samples"
        )
    
    validator = PreflightValidator(
        references_dir=Path(settings.storage.references_dir)
    )
    validation_samples = []
    for sample in samples:
        validation_samples.append({
            "r1_path": sample.r1_path,
            "r2_path": sample.r2_path,
            "metadata": sample.sample_metadata or {
                "sample_id": sample.sample_id,
                "collection_date": str(sample.collection_date.date()) if sample.collection_date else None,
                "host": sample.host,
                "location": sample.location,
                "protocol": sample.protocol,
                "platform": sample.platform,
                "run_id": sample.sequencing_run_id,
                "batch_id": sample.batch_id,
            },
        })
    
    # Get reference path
    from vgap.services.reference_manager import ReferenceManager
    ref_manager = ReferenceManager()
    reference_path = ref_manager.get_reference_path(run.reference_id or "sars-cov-2")
    
    result = validator.validate_run(
        samples=validation_samples,
        mode=run.mode,
        primer_scheme=run.primer_scheme,
        reference_path=reference_path,
    )
    
    if result.blocked:
        # Update run with validation failure
        await update_run_status(
            session, run_id, RunStatus.FAILED,
            error_message=f"Pre-flight validation failed: {result.errors[0].message}"
        )
        await session.commit()
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Pre-flight validation failed",
                "errors": [e.to_dict() for e in result.errors],
                "warnings": [w.to_dict() for w in result.warnings],
            }
        )
    
    # Start the run
    success = await start_run(session, run_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start run"
        )
    
    await session.commit()
    
    return RunStartResponse(
        run_id=run_id,
        status="queued",
        message="Run queued for processing",
        validation_passed=True,
    )


@router.post("/{run_id}/cancel")
async def cancel_run_processing(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_analyst_or_admin),
):
    """Cancel a running or queued run."""
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    # Cancel Celery task if running
    if run.celery_task_id:
        from vgap.worker import celery_app
        celery_app.control.revoke(run.celery_task_id, terminate=True)
    
    success = await cancel_run(session, run_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel run with status: {run.status.value}"
        )
    
    await session.commit()
    
    return {"message": "Run cancelled", "run_id": str(run_id)}


@router.post("/{run_id}/validate", response_model=ValidationResultResponse)
async def validate_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_analyst_or_admin),
):
    """
    Run pre-flight validation without starting the pipeline.
    
    Checks all inputs, metadata, and configuration.
    """
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    samples = await get_run_samples(session, run_id)
    
    validator = PreflightValidator()
    validation_samples = []
    for sample in samples:
        validation_samples.append({
            "r1_path": sample.r1_path,
            "r2_path": sample.r2_path,
            "metadata": sample.metadata,
        })
    
    result = validator.validate_run(
        samples=validation_samples,
        mode=run.mode,
        primer_scheme=run.primer_scheme,
    )
    
    return ValidationResultResponse(
        passed=result.passed,
        status=result.status.value,
        errors=[{
            "code": e.code.value,
            "message": e.message,
            "field": e.field,
            "remediation": e.remediation,
        } for e in result.errors],
        warnings=[{
            "code": w.code.value,
            "message": w.message,
            "field": w.field,
            "remediation": w.remediation,
        } for w in result.warnings],
        sample_count=len(samples),
    )


@router.get("/{run_id}/provenance", response_model=ProvenanceResponse)
async def get_run_provenance(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete provenance for a run.
    
    Only available for completed runs.
    """
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    if run.status not in [RunStatus.COMPLETED, RunStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provenance only available for completed runs"
        )
    
    # Load provenance from results directory
    results_dir = Path(settings.storage.results_dir) / str(run_id)
    provenance_path = results_dir / "provenance.json"
    
    if not provenance_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provenance file not found"
        )
    
    import json
    with open(provenance_path) as f:
        provenance = json.load(f)
    
    return ProvenanceResponse(**provenance)
