"""
VGAP User Service

Database-backed user management with proper authentication.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import structlog
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vgap.models import User, UserRole, AuditLog, AuditAction

logger = structlog.get_logger()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


async def create_user(
    session: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = UserRole.ANALYST,
    created_by: Optional[UUID] = None,
) -> User:
    """
    Create a new user in the database.
    
    Args:
        session: Database session
        email: User email (unique)
        password: Plain text password (will be hashed)
        full_name: User's full name
        role: User role (default: ANALYST)
        created_by: ID of admin creating the user
    
    Returns:
        Created User object
    
    Raises:
        ValueError: If email already exists
    """
    # Check if email exists
    existing = await session.execute(
        select(User).where(User.email == email)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"User with email {email} already exists")
    
    # Create user
    user = User(
        id=uuid4(),
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    
    session.add(user)
    await session.flush()
    
    # Audit log
    if created_by:
        audit = AuditLog(
            id=uuid4(),
            user_id=created_by,
            action=AuditAction.CREATE,
            resource_type="user",
            resource_id=str(user.id),
            details={"email": email, "role": role.value},
            timestamp=datetime.utcnow(),
        )
        session.add(audit)
    
    logger.info("User created", user_id=str(user.id), email=email, role=role.value)
    
    return user


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Get a user by their ID."""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get a user by their email."""
    result = await session.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> Optional[User]:
    """
    Authenticate a user with email and password.
    
    Args:
        session: Database session
        email: User email
        password: Plain text password
    
    Returns:
        User object if authentication successful, None otherwise
    """
    user = await get_user_by_email(session, email)
    
    if not user:
        logger.warning("Authentication failed: user not found", email=email)
        return None
    
    if not user.is_active:
        logger.warning("Authentication failed: user deactivated", email=email)
        return None
    
    if not verify_password(password, user.hashed_password):
        logger.warning("Authentication failed: invalid password", email=email)
        return None
    
    # Update last login
    await session.execute(
        update(User).where(User.id == user.id).values(last_login=datetime.utcnow())
    )
    
    logger.info("User authenticated", user_id=str(user.id), email=email)
    
    return user


async def update_user(
    session: AsyncSession,
    user_id: UUID,
    updated_by: UUID,
    **kwargs,
) -> Optional[User]:
    """
    Update user attributes.
    
    Args:
        session: Database session
        user_id: ID of user to update
        updated_by: ID of admin making the change
        **kwargs: Fields to update (full_name, role, is_active)
    
    Returns:
        Updated User object
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    
    allowed_fields = {"full_name", "role", "is_active"}
    update_data = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not update_data:
        return user
    
    await session.execute(
        update(User).where(User.id == user_id).values(**update_data)
    )
    
    # Audit log
    audit = AuditLog(
        id=uuid4(),
        user_id=updated_by,
        action=AuditAction.UPDATE,
        resource_type="user",
        resource_id=str(user_id),
        details=update_data,
        timestamp=datetime.utcnow(),
    )
    session.add(audit)
    
    logger.info("User updated", user_id=str(user_id), changes=update_data)
    
    return await get_user_by_id(session, user_id)


async def deactivate_user(
    session: AsyncSession,
    user_id: UUID,
    deactivated_by: UUID,
) -> bool:
    """
    Deactivate a user (soft delete).
    
    Args:
        session: Database session
        user_id: ID of user to deactivate
        deactivated_by: ID of admin making the change
    
    Returns:
        True if successful
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    
    await session.execute(
        update(User).where(User.id == user_id).values(is_active=False)
    )
    
    # Audit log
    audit = AuditLog(
        id=uuid4(),
        user_id=deactivated_by,
        action=AuditAction.DELETE,
        resource_type="user",
        resource_id=str(user_id),
        details={"action": "deactivate"},
        timestamp=datetime.utcnow(),
    )
    session.add(audit)
    
    logger.info("User deactivated", user_id=str(user_id), by=str(deactivated_by))
    
    return True


async def change_password(
    session: AsyncSession,
    user_id: UUID,
    old_password: str,
    new_password: str,
) -> bool:
    """
    Change a user's password.
    
    Args:
        session: Database session
        user_id: ID of user
        old_password: Current password for verification
        new_password: New password to set
    
    Returns:
        True if successful
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    
    if not verify_password(old_password, user.hashed_password):
        logger.warning("Password change failed: invalid old password", user_id=str(user_id))
        return False
    
    await session.execute(
        update(User).where(User.id == user_id).values(
            hashed_password=hash_password(new_password)
        )
    )
    
    logger.info("Password changed", user_id=str(user_id))
    
    return True


async def list_users(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    active_only: bool = True,
) -> tuple[list[User], int]:
    """
    List users with pagination.
    
    Args:
        session: Database session
        skip: Number of records to skip
        limit: Maximum records to return
        active_only: Only return active users
    
    Returns:
        Tuple of (users list, total count)
    """
    query = select(User)
    if active_only:
        query = query.where(User.is_active == True)
    
    # Get total count
    from sqlalchemy import func
    count_query = select(func.count()).select_from(User)
    if active_only:
        count_query = count_query.where(User.is_active == True)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    users = result.scalars().all()
    
    return list(users), total


async def ensure_admin_exists(session: AsyncSession) -> User:
    """
    Ensure at least one admin user exists.
    
    Creates a default admin if none exists using environment variables
    or secure defaults. This should only be called during initialization.
    
    Returns:
        The existing or newly created admin user
    """
    import os
    
    # Check if any admin exists
    result = await session.execute(
        select(User).where(User.role == UserRole.ADMIN, User.is_active == True)
    )
    admin = result.scalar_one_or_none()
    
    if admin:
        return admin
    
    # Create initial admin from environment or generate secure password
    admin_email = os.environ.get("VGAP_ADMIN_EMAIL", "admin@vgap.com")
    admin_password = os.environ.get("VGAP_ADMIN_PASSWORD")
    
    if not admin_password:
        # Generate secure random password and write to secure file
        import secrets
        import os as os_module
        admin_password = secrets.token_urlsafe(16)
        
        # Write password to file ONLY (not logs)
        data_dir = os_module.environ.get("DATA_DIR", "/data")
        creds_path = os_module.path.join(data_dir, ".admin_credentials")
        try:
            os_module.makedirs(data_dir, exist_ok=True)
            with open(creds_path, "w") as f:
                f.write(f"ADMIN_EMAIL={admin_email}\n")
                f.write(f"ADMIN_PASSWORD={admin_password}\n")
                f.write("# DELETE THIS FILE AFTER FIRST LOGIN\n")
            os_module.chmod(creds_path, 0o600)
            logger.warning(
                "No VGAP_ADMIN_PASSWORD set. Generated initial admin password.",
                email=admin_email,
                credentials_file=creds_path,
                warning="See credentials file for password. DELETE AFTER FIRST LOGIN!"
            )
        except Exception as e:
            # Fallback: still log but obscure
            logger.warning(
                "No VGAP_ADMIN_PASSWORD set. Generated initial admin password.",
                email=admin_email,
                password_hint=f"{admin_password[:4]}...{admin_password[-4:]}",
                warning="Could not write credentials file. Password partially shown."
            )
    
    admin = await create_user(
        session=session,
        email=admin_email,
        password=admin_password,
        full_name="System Administrator",
        role=UserRole.ADMIN,
    )
    
    await session.commit()
    
    logger.info("Initial admin user created", email=admin_email)
    
    return admin
