"""
VGAP Run Service

Database-backed run management with Celery task integration.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vgap.models import Run, Sample, RunStatus, SampleStatus, AuditLog, AuditAction

logger = structlog.get_logger()


def generate_run_code() -> str:
    """Generate unique run code."""
    return f"RUN-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


async def create_run(
    session: AsyncSession,
    name: str,
    mode: str,
    user_id: UUID,
    description: Optional[str] = None,
    primer_scheme: Optional[str] = None,
    reference_id: Optional[str] = None,
    parameters: Optional[dict] = None,
    run_parameters: Optional[dict] = None,
    project_id: Optional[UUID] = None,
) -> Run:
    """
    Create a new analysis run.
    
    Args:
        session: Database session
        name: Run name
        mode: Pipeline mode (amplicon/shotgun)
        user_id: ID of user creating the run
        description: Optional description
        primer_scheme: Primer scheme for amplicon mode
        reference_id: Reference genome ID
        parameters: Pipeline parameters
        project_id: Optional project ID
    
    Returns:
        Created Run object
    """
    run = Run(
        id=uuid4(),
        run_code=generate_run_code(),
        name=name,
        description=description,
        status=RunStatus.PENDING,
        mode=mode,
        primer_scheme=primer_scheme,
        reference_id=reference_id,

        parameters=parameters or {},
        run_parameters=run_parameters.model_dump() if hasattr(run_parameters, "model_dump") else (run_parameters or {}),
        user_id=user_id,
        project_id=project_id,
        created_at=datetime.utcnow(),
    )
    
    session.add(run)
    await session.flush()
    
    # Audit log
    audit = AuditLog(
        id=uuid4(),
        user_id=user_id,
        action=AuditAction.CREATE,
        resource_type="run",
        resource_id=str(run.id),
        details={"name": name, "mode": mode},
        timestamp=datetime.utcnow(),
    )
    session.add(audit)
    
    logger.info("Run created", run_id=str(run.id), run_code=run.run_code)
    
    return run


async def add_sample_to_run(
    session: AsyncSession,
    run_id: UUID,
    sample_id: str,
    metadata: dict,
    r1_path: str,
    r2_path: Optional[str] = None,
) -> Sample:
    """
    Add a sample to a run.
    
    Args:
        session: Database session
        run_id: Run ID
        sample_id: Sample identifier
        metadata: Sample metadata
        r1_path: Path to R1 FASTQ
        r2_path: Optional path to R2 FASTQ
    
    Returns:
        Created Sample object
    """
    sample = Sample(
        id=uuid4(),
        run_id=run_id,
        sample_id=sample_id,
        r1_path=r1_path,
        r2_path=r2_path,
        status=SampleStatus.PENDING,
        collection_date=datetime.strptime(metadata.get("collection_date", "2024-01-01"), "%Y-%m-%d"),
        host=metadata.get("host", "human"),
        location=metadata.get("location", ""),
        protocol=metadata.get("protocol", "amplicon"),
        platform=metadata.get("platform", ""),
        sequencing_run_id=metadata.get("run_id", ""),
        batch_id=metadata.get("batch_id", ""),
        is_control=metadata.get("is_control", False),
        control_type=metadata.get("control_type"),
        sample_metadata=metadata,
        created_at=datetime.utcnow(),
    )
    
    session.add(sample)
    await session.flush()
    
    logger.info("Sample added to run", run_id=str(run_id), sample_id=sample_id)
    
    return sample


async def get_run_by_id(
    session: AsyncSession,
    run_id: UUID,
    include_samples: bool = False,
) -> Optional[Run]:
    """Get a run by its ID."""
    query = select(Run).where(Run.id == run_id)
    
    if include_samples:
        query = query.options(
            selectinload(Run.samples).options(
                selectinload(Sample.qc_metrics),
                selectinload(Sample.lineage),
                selectinload(Sample.consensus),
                selectinload(Sample.variants),
            )
        )
    
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_run_by_code(
    session: AsyncSession,
    run_code: str,
) -> Optional[Run]:
    """Get a run by its code."""
    result = await session.execute(
        select(Run).where(Run.run_code == run_code)
    )
    return result.scalar_one_or_none()


async def list_runs(
    session: AsyncSession,
    user_id: Optional[UUID] = None,
    status_filter: Optional[RunStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Run], int]:
    """
    List runs with filtering and pagination.
    
    Args:
        session: Database session
        user_id: Filter by user (None = all users, admin only)
        status_filter: Filter by status
        skip: Number to skip
        limit: Maximum to return
    
    Returns:
        Tuple of (runs, total_count)
    """
    query = select(Run)
    count_query = select(func.count()).select_from(Run)
    
    if user_id:
        query = query.where(Run.user_id == user_id)
        count_query = count_query.where(Run.user_id == user_id)
    
    if status_filter:
        query = query.where(Run.status == status_filter)
        count_query = count_query.where(Run.status == status_filter)
    
    # Get count
    count_result = await session.execute(count_query)
    total = count_result.scalar()
    
    # Get runs
    query = query.order_by(Run.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    runs = result.scalars().all()
    
    return list(runs), total


async def update_run_status(
    session: AsyncSession,
    run_id: UUID,
    status: RunStatus,
    error_message: Optional[str] = None,
) -> bool:
    """
    Update run status.
    
    Args:
        session: Database session
        run_id: Run ID
        status: New status
        error_message: Error message if failed
    
    Returns:
        True if updated
    """
    update_data = {"status": status}
    
    if status == RunStatus.RUNNING:
        update_data["started_at"] = datetime.utcnow()
    elif status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
        update_data["completed_at"] = datetime.utcnow()
    
    if error_message:
        update_data["error_message"] = error_message
    
    result = await session.execute(
        update(Run).where(Run.id == run_id).values(**update_data)
    )
    
    if result.rowcount > 0:
        logger.info("Run status updated", run_id=str(run_id), status=status.value)
        return True
    
    return False


async def update_sample_status(
    session: AsyncSession,
    sample_id: UUID,
    status: SampleStatus,
    error_message: Optional[str] = None,
) -> bool:
    """Update sample status."""
    update_data = {"status": status}
    
    if error_message:
        update_data["error_message"] = error_message
    
    result = await session.execute(
        update(Sample).where(Sample.id == sample_id).values(**update_data)
    )
    
    return result.rowcount > 0


async def get_run_samples(
    session: AsyncSession,
    run_id: UUID,
) -> list[Sample]:
    """Get all samples for a run."""
    result = await session.execute(
        select(Sample).where(Sample.run_id == run_id).order_by(Sample.sample_id)
    )
    return list(result.scalars().all())


async def get_run_sample_count(
    session: AsyncSession,
    run_id: UUID,
) -> int:
    """Get sample count for a run."""
    result = await session.execute(
        select(func.count()).select_from(Sample).where(Sample.run_id == run_id)
    )
    return result.scalar()


async def cancel_run(
    session: AsyncSession,
    run_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Cancel a running or queued run.
    
    Args:
        session: Database session
        run_id: Run to cancel
        user_id: User cancelling the run
    
    Returns:
        True if cancelled
    """
    run = await get_run_by_id(session, run_id)
    if not run:
        return False
    
    if run.status not in [RunStatus.PENDING, RunStatus.QUEUED, RunStatus.RUNNING]:
        return False
    
    await update_run_status(session, run_id, RunStatus.CANCELLED)
    
    # Audit log
    audit = AuditLog(
        id=uuid4(),
        user_id=user_id,
        action=AuditAction.UPDATE,
        resource_type="run",
        resource_id=str(run_id),
        details={"action": "cancel", "previous_status": run.status.value},
        timestamp=datetime.utcnow(),
    )
    session.add(audit)
    
    logger.info("Run cancelled", run_id=str(run_id), by=str(user_id))
    
    return True


async def start_run(
    session: AsyncSession,
    run_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Start a pending run by queueing it for processing.
    
    Args:
        session: Database session
        run_id: Run to start
        user_id: User starting the run
    
    Returns:
        True if started
    """
    from vgap.services.pipeline import process_run
    
    run = await get_run_by_id(session, run_id)
    if not run:
        return False
    
    if run.status != RunStatus.PENDING:
        return False
    
    # Update status to queued
    await update_run_status(session, run_id, RunStatus.QUEUED)
    await session.commit()
    
    try:
        # Queue Celery task
        # Use apply_async to ensure we can catch connection errors
        process_run.apply_async(args=[str(run_id)], retry=True, retry_policy={
            'max_retries': 3,
            'interval_start': 0,
            'interval_step': 0.2,
            'interval_max': 0.2,
        })
    except Exception as e:
        logger.error("Failed to queue run task", run_id=str(run_id), error=str(e))
        
        # Revert status to FAILED so user knows it didn't start
        await update_run_status(
            session, 
            run_id, 
            RunStatus.FAILED, 
            error_message=f"System error: Failed to queue task. {str(e)}"
        )
        await session.commit()
        return False
    
    # Audit log
    audit = AuditLog(
        id=uuid4(),
        user_id=user_id,
        action=AuditAction.UPDATE,
        resource_type="run",
        resource_id=str(run_id),
        details={"action": "start"},
        timestamp=datetime.utcnow(),
    )
    session.add(audit)
    
    logger.info("Run started", run_id=str(run_id), by=str(user_id))
    
    return True
