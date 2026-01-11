"""
VGAP FastAPI Main Application

Production-ready API server with real health checks and middleware.
"""

import time
from contextlib import asynccontextmanager
from datetime import datetime

import redis
import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from sqlalchemy import select, func

from vgap.config import get_settings
from vgap.services.database import init_db, get_session, engine
from vgap.services.user_service import ensure_admin_exists

settings = get_settings()
logger = structlog.get_logger()

# Track application start time
APP_START_TIME = datetime.utcnow()

# Prometheus metrics
REQUEST_COUNT = Counter(
    "vgap_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "vgap_api_request_latency_seconds",
    "API request latency",
    ["method", "endpoint"]
)
VALIDATION_BLOCKS = Counter(
    "vgap_validation_blocks_total",
    "Pre-flight validation blocks",
    ["error_code"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting VGAP API server", version=settings.api.version)
    
    # Initialize database
    await init_db()
    
    # Ensure admin user exists
    async for session in get_session():
        try:
            await ensure_admin_exists(session)
        except Exception as e:
            logger.warning("Could not ensure admin exists", error=str(e))
        break
    
    logger.info("VGAP API server ready")
    
    yield
    
    # Cleanup
    await engine.dispose()
    logger.info("VGAP API server stopped")


app = FastAPI(
    title="VGAP - Viral Genomics Analysis Platform",
    description="Production-grade platform for viral genome analysis",
    version=settings.api.version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log requests and collect metrics."""
    start_time = time.time()
    
    # Extract endpoint for metrics (normalize path params)
    endpoint = request.url.path
    for key in ["run_id", "sample_id", "report_id", "user_id"]:
        if f"{{{key}}}" not in endpoint:
            # Replace UUIDs with placeholder
            import re
            endpoint = re.sub(
                r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                "/{id}",
                endpoint
            )
    
    try:
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(duration)
        
        # Log request
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=500
        ).inc()
        
        logger.exception(
            "Request failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
        )
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.exception("Unhandled exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


# ============================================================================
# HEALTH ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    
    Returns overall health status based on component checks.
    """
    components = {}
    overall_healthy = True
    
    # Database check
    try:
        from vgap.services.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(select(func.now()))
        components["database"] = "healthy"
    except Exception as e:
        components["database"] = "unhealthy"
        overall_healthy = False
        logger.error("Database health check failed", error=str(e))
    
    # Redis check
    try:
        r = redis.from_url(settings.redis.url)
        r.ping()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = "unhealthy"
        overall_healthy = False
        logger.error("Redis health check failed", error=str(e))
    
    # Worker check (non-blocking)
    try:
        from vgap.worker import celery_app
        inspect = celery_app.control.inspect(timeout=1)
        ping = inspect.ping() or {}
        worker_count = len(ping)
        components["workers"] = f"{worker_count} active"
        if worker_count == 0:
            components["workers"] = "no workers"
            # Don't mark as unhealthy - workers may be scaling
    except Exception:
        components["workers"] = "unknown"
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "version": settings.api.version,
        "components": components,
        "uptime_seconds": (datetime.utcnow() - APP_START_TIME).total_seconds(),
    }


@app.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_check():
    """
    Kubernetes readiness probe.
    
    Returns 503 if not ready to accept traffic.
    """
    try:
        from vgap.services.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(select(func.now()))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "reason": "database unavailable"}
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "VGAP - Viral Genomics Analysis Platform",
        "version": settings.api.version,
        "documentation": "/api/docs",
        "health": "/health",
    }


# ============================================================================
# METRICS ENDPOINT
# ============================================================================

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ============================================================================
# INCLUDE ROUTERS
# ============================================================================

from vgap.api.routes import auth, runs, samples, reports, admin

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(runs.router, prefix="/api/v1/runs", tags=["Runs"])
app.include_router(samples.router, prefix="/api/v1/samples", tags=["Samples"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


# ============================================================================
# UPLOAD ENDPOINT
# ============================================================================

from fastapi import UploadFile, File

@app.post("/api/v1/upload/{session_id}")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
):
    """
    Upload a file to a session.
    
    Files are streamed to disk without loading into memory.
    """
    from vgap.services.upload import UploadService
    
    upload_service = UploadService()
    
    # Validate filename
    is_valid, error = upload_service.validate_filename(file.filename)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": error}
        )
    
    # Stream upload
    async def file_stream():
        while chunk := await file.read(65536):
            yield chunk
    
    try:
        path, checksum, size = await upload_service.stream_upload(
            session_id=session_id,
            filename=file.filename,
            stream=file_stream(),
        )
        
        return {
            "filename": file.filename,
            "size": size,
            "checksum": checksum,
        }
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)}
        )


@app.post("/api/v1/upload/session")
async def create_upload_session():
    """Create a new upload session."""
    from vgap.services.upload import UploadService
    
    upload_service = UploadService()
    session_id = await upload_service.create_upload_session()
    
    return {"session_id": session_id}
