"""
VGAP Pydantic Schemas

Request/response models for the API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# =============================================================================
# ENUMS
# =============================================================================

class RunStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SampleStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineMode(str, Enum):
    AMPLICON = "amplicon"
    SHOTGUN = "shotgun"


class UserRole(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


# =============================================================================
# AUTH SCHEMAS
# =============================================================================

class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str
    exp: datetime
    role: UserRole


class UserCreate(BaseModel):
    """User creation request."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole = UserRole.ANALYST


class UserResponse(BaseModel):
    """User response (no password)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class UserLogin(BaseModel):
    """Login request."""
    email: EmailStr
    password: str


# =============================================================================
# SAMPLE SCHEMAS
# =============================================================================

class SampleMetadata(BaseModel):
    """Required sample metadata."""
    sample_id: str = Field(..., min_length=1, max_length=100)
    collection_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    host: str = Field(..., min_length=1, max_length=50)
    location: str = Field(..., min_length=1, max_length=255)
    protocol: str = Field(..., pattern=r"^(amplicon|shotgun|capture)$")
    platform: str = Field(..., min_length=1, max_length=100)
    run_id: str = Field(..., min_length=1, max_length=100)
    batch_id: str = Field(..., min_length=1, max_length=100)
    clinical_group: Optional[str] = Field(None, max_length=100)
    is_control: bool = False
    control_type: Optional[str] = Field(None, pattern=r"^(positive|negative)$")
    notes: Optional[str] = None
    
    @field_validator("collection_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        from datetime import datetime as dt
        try:
            dt.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD.")
        return v


class SampleCreate(BaseModel):
    """Sample creation with file paths."""
    metadata: SampleMetadata
    r1_filename: str
    r2_filename: Optional[str] = None


class SampleResponse(BaseModel):
    """Sample response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    sample_id: str
    collection_date: datetime
    host: str
    location: str
    protocol: str
    status: SampleStatus
    error_message: Optional[str] = None
    created_at: datetime


class SampleDetailResponse(SampleResponse):
    """Detailed sample response with results."""
    qc_metrics: Optional[dict[str, Any]] = None
    consensus_info: Optional[dict[str, Any]] = None
    variant_count: int = 0
    lineage: Optional[dict[str, Any]] = None


# =============================================================================
# RUN SCHEMAS
# =============================================================================

class RunParameters(BaseModel):
    """Configurable run parameters."""
    min_depth: int = Field(10, ge=1, le=1000)
    min_allele_freq: float = Field(0.5, ge=0.0, le=1.0)
    min_variant_freq: float = Field(0.02, ge=0.0, le=1.0)
    min_read_length: int = Field(50, ge=20, le=500)
    min_base_quality: int = Field(20, ge=0, le=40)
    enable_host_removal: bool = True
    enable_phylogeny: bool = True


class RunCreate(BaseModel):
    """Run creation request."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    mode: PipelineMode
    primer_scheme: Optional[str] = None
    reference_id: Optional[str] = None
    parameters: RunParameters = Field(default_factory=RunParameters)
    samples: list[SampleCreate]
    project_id: Optional[UUID] = None
    
    @field_validator("primer_scheme")
    @classmethod
    def validate_primer_scheme(cls, v: Optional[str], info) -> Optional[str]:
        mode = info.data.get("mode")
        if mode == PipelineMode.AMPLICON and not v:
            raise ValueError("Primer scheme is required for amplicon mode")
        return v


class RunResponse(BaseModel):
    """Run response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    run_code: str
    name: str
    description: Optional[str]
    status: RunStatus
    mode: PipelineMode
    primer_scheme: Optional[str]
    sample_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RunDetailResponse(RunResponse):
    """Detailed run response."""
    parameters: dict[str, Any]
    samples: list[SampleResponse]
    provenance: Optional[dict[str, Any]] = None


class RunStatusUpdate(BaseModel):
    """Run status update."""
    status: RunStatus
    error_message: Optional[str] = None


# =============================================================================
# VALIDATION SCHEMAS
# =============================================================================

class ValidationError(BaseModel):
    """Single validation error."""
    code: str
    message: str
    field: Optional[str] = None
    sample_id: Optional[str] = None
    remediation: Optional[str] = None


class ValidationWarning(BaseModel):
    """Single validation warning."""
    code: str
    message: str
    field: Optional[str] = None
    sample_id: Optional[str] = None


class ValidationResult(BaseModel):
    """Complete validation result."""
    status: str
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []
    metadata: dict[str, Any] = {}


# =============================================================================
# RESULTS SCHEMAS
# =============================================================================

class QCMetricsResponse(BaseModel):
    """QC metrics response."""
    model_config = ConfigDict(from_attributes=True)
    
    raw_reads: int
    trimmed_reads: int
    q20_rate: float
    q30_rate: float
    gc_content: float
    mapped_reads: int
    mapping_rate: float
    mean_depth: float
    coverage_10x: float
    coverage_30x: float
    qc_pass: bool


class VariantResponse(BaseModel):
    """Variant response."""
    model_config = ConfigDict(from_attributes=True)
    
    chrom: str
    pos: int
    ref: str
    alt: str
    depth: int
    allele_freq: float
    gene: Optional[str] = None
    aa_change: Optional[str] = None
    effect: Optional[str] = None
    is_consensus: bool
    is_minor: bool
    is_flagged: bool
    filter_status: str


class LineageResponse(BaseModel):
    """Lineage assignment response."""
    model_config = ConfigDict(from_attributes=True)
    
    pangolin_lineage: Optional[str] = None
    pangolin_version: Optional[str] = None
    nextclade_clade: Optional[str] = None
    nextclade_version: Optional[str] = None
    confidence_score: Optional[float] = None


class ConsensusResponse(BaseModel):
    """Consensus sequence info."""
    model_config = ConfigDict(from_attributes=True)
    
    sequence_length: int
    n_count: int
    n_percentage: float
    min_depth: int
    min_allele_freq: float


# =============================================================================
# PROVENANCE SCHEMAS
# =============================================================================

class ProvenanceFile(BaseModel):
    """File provenance."""
    path: str
    sha256: str
    size_bytes: int


class ProvenanceSoftware(BaseModel):
    """Software provenance."""
    name: str
    version: str
    container: Optional[str] = None


class ProvenanceDatabase(BaseModel):
    """Database provenance."""
    name: str
    version: str
    checksum: str


class Provenance(BaseModel):
    """Complete provenance record."""
    run_id: UUID
    timestamp: datetime
    user_id: UUID
    inputs: dict[str, Any]
    parameters: dict[str, Any]
    software: list[ProvenanceSoftware]
    databases: list[ProvenanceDatabase]
    random_seeds: dict[str, int]
    outputs: dict[str, str]
    validation_status: dict[str, str]


# =============================================================================
# REPORT SCHEMAS
# =============================================================================

class ReportRequest(BaseModel):
    """Report generation request."""
    format: str = Field("html", pattern=r"^(html|pdf)$")
    include_figures: bool = True
    include_tables: bool = True
    include_provenance: bool = True


class ReportResponse(BaseModel):
    """Report response."""
    report_id: UUID
    run_id: UUID
    format: str
    file_path: str
    generated_at: datetime
    checksum: str


# =============================================================================
# PAGINATION SCHEMAS
# =============================================================================

class PaginationParams(BaseModel):
    """Pagination parameters."""
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    items: list[Any]
    total: int
    skip: int
    limit: int
    
    @property
    def has_more(self) -> bool:
        return self.skip + len(self.items) < self.total


# =============================================================================
# HEALTH & METRICS
# =============================================================================

class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    version: str
    database: str
    redis: str
    workers: int


class MetricsSummary(BaseModel):
    """Metrics summary."""
    runs_total: int
    runs_completed: int
    runs_failed: int
    samples_processed: int
    avg_runtime_seconds: float
