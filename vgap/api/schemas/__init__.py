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
    QC_COMPLETE = "qc_complete"
    MAPPING_COMPLETE = "mapping_complete"
    VARIANTS_COMPLETE = "variants_complete"
    COMPLETE = "complete"
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


class ReportFormat(str, Enum):
    HTML = "html"
    PDF = "pdf"


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


class UserUpdate(BaseModel):
    """User update request."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)



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


class VariantListResponse(BaseModel):
    """List of variants for a sample."""
    sample_id: UUID
    total: int
    variants: list[VariantResponse]


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
    qc_metrics: Optional[QCMetricsResponse] = None
    consensus_info: Optional[ConsensusResponse] = Field(None, alias="consensus")
    variant_count: int = 0
    lineage: Optional[LineageResponse] = None


# =============================================================================
# RUN SCHEMAS
# =============================================================================

from vgap.api.schemas.parameters import RunParameters


class RunCreate(BaseModel):
    """Run creation request."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    mode: PipelineMode
    primer_scheme: Optional[str] = None
    reference_id: Optional[str] = None
    run_parameters: Optional[RunParameters] = None
    parameters: dict[str, Any] = Field(default_factory=dict, description="Legacy parameters")
    samples: list[SampleCreate]
    project_id: Optional[UUID] = None
    upload_session_id: Optional[str] = None
    
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
    samples: list[SampleDetailResponse]
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


class ReportGenerateRequest(BaseModel):
    """Request to generate a fresh report."""
    title: Optional[str] = None
    format: ReportFormat = ReportFormat.HTML
    include_figures: bool = True
    include_tables: bool = True
    include_provenance: bool = True
    include_methods: bool = True
    figure_format: Optional[str] = "svg"
    figure_dpi: int = 300


class ReportResponse(BaseModel):
    """Report response."""
    report_id: UUID
    run_id: UUID
    format: str
    generated_at: datetime
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None


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


class SampleListResponse(PaginatedResponse):
    """Paginated list of samples."""
    items: list[SampleResponse]


class RunListResponse(PaginatedResponse):
    """Paginated list of runs."""
    items: list[RunResponse]


class UserListResponse(PaginatedResponse):
    """Paginated list of users."""
    items: list[UserResponse]


class RunStartResponse(BaseModel):
    """Run start confirmation."""
    run_id: UUID
    status: str
    message: str
    validation_passed: bool


class ValidationResultResponse(BaseModel):
    """Results of pre-flight run validation."""
    passed: bool
    status: str
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    sample_count: int


class ProvenanceResponse(Provenance):
    """Response model for provenance."""
    pass


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


class DatabaseInfo(BaseModel):
    """Reference database info."""
    name: str
    version: Optional[str]
    checksum: Optional[str]
    updated_at: Optional[datetime]
    updated_by: Optional[str]
    path: Optional[str]  # Was path: str but for uninstalled it is None
    status: str          # New field for "installed", "not_installed" etc


class DatabaseUpdateResponse(BaseModel):
    """Database update response."""
    name: str
    old_version: Optional[str]
    new_version: str
    checksum: str
    updated_at: datetime


class AuditLogEntry(BaseModel):
    """Single audit log entry."""
    id: UUID
    user_id: UUID
    action: str
    resource_type: str
    resource_id: str
    details: Optional[dict[str, Any]]
    timestamp: datetime
    ip_address: Optional[str]


class AuditLogResponse(PaginatedResponse):
    """Audit log response."""
    items: list[AuditLogEntry]


class SystemStatus(BaseModel):
    """System health status."""
    status: str
    database: str
    redis: str
    workers: list[str]
    workers_active: int
    disk_usage_percent: float
    version: str
    uptime_seconds: float
