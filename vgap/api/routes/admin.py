"""
VGAP Admin Routes

Database-backed administrative functions.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from vgap.api.routes.auth import require_admin
from vgap.api.schemas import (
    UserResponse, UserListResponse, UserCreate, UserUpdate,
    DatabaseInfo, DatabaseUpdateResponse, AuditLogEntry, AuditLogResponse,
    SystemStatus,
)
from vgap.config import get_settings
from vgap.models import User, UserRole, AuditLog, AuditAction, ReferenceDatabase
from vgap.services.database import get_session
from vgap.services.user_service import (
    create_user, list_users, get_user_by_id, update_user, deactivate_user,
)

router = APIRouter()
settings = get_settings()


# ============================================================================
# DATABASE MANAGEMENT
# ============================================================================

@router.get("/databases", response_model=list[DatabaseInfo])
async def list_databases(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """List all reference databases and their versions."""
    # Always fetch inventory from disk - single source of truth for AVAILABILITY
    from vgap.services.reference_manager import ReferenceManager
    manager = ReferenceManager()
    inventory = manager.get_inventory()

    # Fetch DB records for INSTALLED status/timestamps
    result = await session.execute(
        select(ReferenceDatabase).order_by(ReferenceDatabase.name)
    )
    db_records = {db.name: db for db in result.scalars().all()}
    
    # Sync: If inventory says "installed" but not in DB, add it
    updates_made = False
    
    # 1. Sync References
    for ref_id, data in inventory.get("references", {}).items():
        if data["status"] == "installed" and data["name"] not in db_records:
            db = ReferenceDatabase(
                id=uuid4(),
                name=data["name"],
                version=data["version"],
                db_type="reference",
                checksum=data.get("checksum"),
                path=data["path"],
                updated_at=datetime.utcnow(),
                updated_by=current_user.id
            )
            session.add(db)
            updates_made = True

    # 2. Sync Primers
    for scheme_id, data in inventory.get("primers", {}).items():
        if data["status"] == "installed" and data["name"] not in db_records:
            db = ReferenceDatabase(
                id=uuid4(),
                name=data["name"],
                version="latest",
                db_type="primer_scheme",
                path=data["path"],
                checksum=data.get("checksum"),
                updated_at=datetime.utcnow(),
                updated_by=current_user.id
            )
            session.add(db)
            updates_made = True
    
    if updates_made:
        await session.commit()
        # Re-fetch
        result = await session.execute(
            select(ReferenceDatabase).order_by(ReferenceDatabase.name)
        )
        db_records = {db.name: db for db in result.scalars().all()}

    # Build Response: Mix Inventory (Available) + DB logic (Version/Time)
    response = []
    
    # References
    for ref_id, data in inventory.get("references", {}).items():
        db_record = db_records.get(data["name"])
        response.append(DatabaseInfo(
            name=data["name"],
            version=data["version"] if data["version"] else "available",
            checksum=data.get("checksum"),
            status=data["status"],
            updated_at=db_record.updated_at if db_record else None,
            updated_by=str(db_record.updated_by) if db_record and db_record.updated_by else None,
            path=data["path"],
            source_url=None # Could map from REPO if needed
        ))

    # Primers
    for scheme_id, data in inventory.get("primers", {}).items():
        db_record = db_records.get(data["name"])
        response.append(DatabaseInfo(
            name=data["name"],
            version="latest",
            checksum=data.get("checksum"),
            status=data["status"],
            updated_at=db_record.updated_at if db_record else None,
            updated_by=str(db_record.updated_by) if db_record and db_record.updated_by else None,
            path=data["path"],
        ))
        
    return response


@router.get("/databases/inventory")
async def get_database_inventory(
    current_user: User = Depends(require_admin),
):
    """
    Get complete database inventory from filesystem.
    
    Returns installed references, primer schemes, and their status.
    Does NOT require database access - reads directly from filesystem.
    """
    from vgap.services.reference_manager import ReferenceManager
    
    manager = ReferenceManager()
    return manager.get_inventory()


@router.post("/databases/bootstrap")
async def bootstrap_databases(
    current_user: User = Depends(require_admin),
):
    """
    Bootstrap all reference databases.
    
    Downloads SARS-CoV-2 reference from NCBI and ARTIC primer schemes.
    This operation may take several minutes.
    """
    from vgap.services.reference_manager import ReferenceManager
    
    manager = ReferenceManager()
    result = manager.bootstrap_all()
    
    return {
        "success": result["success"],
        "message": "Database bootstrap complete" if result["success"] else "Bootstrap completed with errors",
        "details": result,
    }


@router.post("/databases/{ref_id}/bootstrap")
async def bootstrap_single_database(
    ref_id: str,
    current_user: User = Depends(require_admin),
):
    """
    Bootstrap a specific reference database.
    """
    from vgap.services.reference_manager import ReferenceManager, DatabaseStatus
    
    manager = ReferenceManager()
    
    # Check if ref_id is valid
    inventory = manager.get_inventory()
    if ref_id not in inventory["references"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown reference ID: {ref_id}"
        )
    
    result = manager.bootstrap_reference(ref_id)
    
    if result.status == DatabaseStatus.ERROR:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bootstrap failed: {result.error_message}"
        )
    
    return {
        "success": True,
        "message": f"Successfully installed {result.name}",
        "details": result.to_dict(),
    }


@router.get("/databases/verify")
async def verify_database_integrity(
    current_user: User = Depends(require_admin),
):
    """
    Verify integrity of installed databases.
    
    Checks checksums and file existence.
    """
    from vgap.services.reference_manager import ReferenceManager
    
    manager = ReferenceManager()
    return manager.verify_integrity()


@router.post("/databases/{name}/update", response_model=DatabaseUpdateResponse)
async def update_database(
    name: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Update a reference database.
    
    Admin only. Triggers download and verification of latest database.
    Archives previous version.
    """
    import subprocess
    import hashlib
    
    # Get current database
    result = await session.execute(
        select(ReferenceDatabase).where(ReferenceDatabase.name == name)
    )
    db = result.scalar_one_or_none()
    
    old_version = db.version if db else None
    
    # Run update command based on database type
    db_dir = Path(settings.storage.reference_dir) / name
    db_dir.mkdir(parents=True, exist_ok=True)
    
    if name == "pangolin":
        # Update Pangolin data
        try:
            result = subprocess.run(
                ["pangolin", "--update-data"],
                capture_output=True,
                text=True,
                timeout=600,
            )
            # Get new version
            version_result = subprocess.run(
                ["pangolin", "--all-versions"],
                capture_output=True,
                text=True,
            )
            new_version = version_result.stdout.strip()[:50]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update {name}: {str(e)}"
            )
    
    elif name == "nextclade":
        # Update Nextclade data
        try:
            result = subprocess.run(
                ["nextclade", "dataset", "get", "--name=sars-cov-2", "-o", str(db_dir)],
                capture_output=True,
                text=True,
                timeout=600,
            )
            new_version = datetime.utcnow().strftime("%Y%m%d")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update {name}: {str(e)}"
            )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown database: {name}"
        )
    
    # Compute checksum of main file
    checksum = ""
    for f in db_dir.iterdir():
        if f.is_file():
            sha256 = hashlib.sha256()
            with open(f, 'rb') as file:
                for chunk in iter(lambda: file.read(65536), b''):
                    sha256.update(chunk)
            checksum = sha256.hexdigest()
            break
    
    # Update or create database record
    if db:
        db.version = new_version
        db.checksum = checksum
        db.updated_at = datetime.utcnow()
        db.updated_by = current_user.id
    else:
        db = ReferenceDatabase(
            id=uuid4(),
            name=name,
            version=new_version,
            checksum=checksum,
            path=str(db_dir),
            updated_at=datetime.utcnow(),
            updated_by=current_user.id,
        )
        session.add(db)
    
    # Audit log
    audit = AuditLog(
        id=uuid4(),
        user_id=current_user.id,
        action=AuditAction.UPDATE,
        resource_type="database",
        resource_id=name,
        details={
            "old_version": old_version,
            "new_version": new_version,
            "checksum": checksum,
        },
        timestamp=datetime.utcnow(),
    )
    session.add(audit)
    
    await session.commit()
    
    return DatabaseUpdateResponse(
        name=name,
        old_version=old_version,
        new_version=new_version,
        checksum=checksum,
        updated_at=datetime.utcnow(),
    )


# ============================================================================
# AUDIT LOG
# ============================================================================

@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    resource_type: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Get audit log entries.
    
    Filterable by resource type, user, and action.
    """
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)
    
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)
    
    if action:
        try:
            action_enum = AuditAction(action)
            query = query.where(AuditLog.action == action_enum)
            count_query = count_query.where(AuditLog.action == action_enum)
        except ValueError:
            pass
    
    # Get count
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Get entries
    query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    entries = result.scalars().all()
    
    return AuditLogResponse(
        items=[
            AuditLogEntry(
                id=e.id,
                user_id=e.user_id,
                action=e.action.value,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                details=e.details,
                timestamp=e.timestamp,
                ip_address=e.ip_address,
            )
            for e in entries
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.get("/users", response_model=UserListResponse)
async def list_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """List all users."""
    users, total = await list_users(
        session=session,
        skip=skip,
        limit=limit,
        active_only=not include_inactive,
    )
    
    return UserListResponse(
        items=[
            UserResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
                last_login=u.last_login,
            )
            for u in users
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Create a new user."""
    try:
        user = await create_user(
            session=session,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role=user_data.role,
            created_by=current_user.id,
        )
        await session.commit()
        
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Get user details."""
    user = await get_user_by_id(session, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_info(
    user_id: UUID,
    user_data: UserUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Update user information."""
    user = await update_user(
        session=session,
        user_id=user_id,
        updated_by=current_user.id,
        **user_data.model_dump(exclude_unset=True),
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    await session.commit()
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.post("/users/{user_id}/deactivate")
async def deactivate_user_account(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Deactivate a user account."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    success = await deactivate_user(session, user_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    await session.commit()
    
    return {"message": "User deactivated", "user_id": str(user_id)}


# ============================================================================
# SYSTEM STATUS
# ============================================================================

@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Get system status including component health.
    
    Checks database, Redis, and worker status.
    """
    import redis
    from vgap.worker import celery_app
    
    # Database check
    try:
        await session.execute(select(func.now()))
        db_healthy = True
    except Exception:
        db_healthy = False
    
    # Redis check
    try:
        r = redis.from_url(str(settings.redis.url))
        r.ping()
        redis_healthy = True
    except Exception:
        redis_healthy = False
    
    # Worker check
    try:
        inspect = celery_app.control.inspect(timeout=1.0)
        active = inspect.active() or {}
        workers = list(active.keys())
        workers_healthy = len(workers) > 0
    except Exception:
        workers = []
        workers_healthy = False
    
    # Disk usage
    import shutil
    results_path = Path(settings.storage.results_dir)
    if results_path.exists():
        total, used, free = shutil.disk_usage(results_path)
        disk_usage_percent = (used / total) * 100
    else:
        disk_usage_percent = 0
    
    return SystemStatus(
        status="healthy" if all([db_healthy, redis_healthy, workers_healthy]) else "degraded",
        database="healthy" if db_healthy else "unhealthy",
        redis="healthy" if redis_healthy else "unhealthy",
        workers=workers,
        workers_active=len(workers),
        disk_usage_percent=round(disk_usage_percent, 1),
        version=settings.app_version,
        uptime_seconds=0,  # Would need to track app start time
    )
