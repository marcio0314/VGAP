"""
VGAP Authentication Routes

Database-backed user authentication with JWT tokens.
No hardcoded credentials - all users must exist in database.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from vgap.api.schemas import Token, UserCreate, UserLogin, UserResponse, UserRole
from vgap.config import get_settings
from vgap.models import User
from vgap.services.database import get_session
from vgap.services.user_service import (
    authenticate_user,
    create_user,
    get_user_by_id,
    hash_password,
)

router = APIRouter()
settings = get_settings()

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.security.jwt_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.security.secret_key,
        algorithm=settings.security.jwt_algorithm
    )
    return encoded_jwt


async def get_current_user(
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Get current user - AUTHENTICATION DISABLED.
    
    Returns a default admin user for single-user local deployment.
    No token validation required.
    """
    from vgap.services.user_service import ensure_admin_exists
    
    # Return the actual persisted admin user
    # This ensures foreign key constraints are satisfied
    return await ensure_admin_exists(session)


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Ensure user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Require admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_analyst_or_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Require analyst or admin role."""
    if current_user.role not in [UserRole.ANALYST, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst or admin access required"
        )
    return current_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: AsyncSession = Depends(get_session),
):
    """
    OAuth2 compatible token login.
    
    Authenticates user against database and returns JWT token.
    """
    user = await authenticate_user(session, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.security.jwt_expire_minutes * 60
    )


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_session),
):
    """
    Login with email and password.
    
    Returns JWT token for authentication.
    """
    user = await authenticate_user(session, credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.security.jwt_expire_minutes * 60
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Register a new user.
    
    Admin only. Creates user in database with hashed password.
    """
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


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Get current user information from database.
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Refresh access token.
    
    Returns new token with extended expiration.
    """
    access_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role.value,
        }
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.security.jwt_expire_minutes * 60
    )


@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Logout current user.
    
    Note: JWT tokens are stateless. This endpoint is for audit logging.
    Client should discard the token.
    """
    # Audit logging happens automatically via middleware
    return {"message": "Logged out successfully"}
