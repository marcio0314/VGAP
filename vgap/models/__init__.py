"""
VGAP Database Models

SQLAlchemy models for the viral genomics platform.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    
    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


# =============================================================================
# ENUMS
# =============================================================================

class RunStatus(str, PyEnum):
    """Pipeline run status."""
    PENDING = "pending"
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SampleStatus(str, PyEnum):
    """Individual sample status."""
    PENDING = "pending"
    PROCESSING = "processing"
    QC_COMPLETE = "qc_complete"
    MAPPING_COMPLETE = "mapping_complete"
    VARIANTS_COMPLETE = "variants_complete"
    COMPLETE = "complete"
    COMPLETED = "completed"  # Alias
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineMode(str, PyEnum):
    """Analysis mode."""
    AMPLICON = "amplicon"
    SHOTGUN = "shotgun"


class UserRole(str, PyEnum):
    """User role for RBAC."""
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"


class AuditAction(str, PyEnum):
    """Audit log action types."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACCESS = "access"
    EXPORT = "export"
    LOGIN = "login"
    LOGOUT = "logout"
    DB_UPDATE = "db_update"


# =============================================================================
# MIXINS
# =============================================================================

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class UUIDMixin:
    """Mixin for UUID primary key."""
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )


# =============================================================================
# USER & AUTH MODELS
# =============================================================================

class User(Base, UUIDMixin, TimestampMixin):
    """User account."""
    
    __tablename__ = "users"
    
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.ANALYST,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    runs: Mapped[list["Run"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")
    
    __table_args__ = (
        Index("ix_users_email", "email"),
    )


# =============================================================================
# PROJECT & RUN MODELS
# =============================================================================

class Project(Base, UUIDMixin, TimestampMixin):
    """Project grouping for runs."""
    
    __tablename__ = "projects"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    
    # Relationships
    runs: Mapped[list["Run"]] = relationship(back_populates="project")
    
    __table_args__ = (
        Index("ix_projects_owner", "owner_id"),
    )


class Run(Base, UUIDMixin, TimestampMixin):
    """Pipeline run."""
    
    __tablename__ = "runs"
    
    # Identifiers
    run_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Status
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus),
        default=RunStatus.PENDING,
        nullable=False,
    )
    
    # Configuration
    mode: Mapped[PipelineMode] = mapped_column(Enum(PipelineMode), nullable=False)
    primer_scheme: Mapped[Optional[str]] = mapped_column(String(100))
    reference_id: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Parameters (stored as JSONB for flexibility)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Execution info
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    progress: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    current_stage: Mapped[Optional[str]] = mapped_column(String(100))
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Provenance
    provenance: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    
    # Storage paths
    input_dir: Mapped[Optional[str]] = mapped_column(String(500))
    output_dir: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Foreign keys
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id"),
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="runs")
    project: Mapped[Optional["Project"]] = relationship(back_populates="runs")
    samples: Mapped[list["Sample"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        Index("ix_runs_status", "status"),
        Index("ix_runs_user", "user_id"),
        Index("ix_runs_created", "created_at"),
    )


class Sample(Base, UUIDMixin, TimestampMixin):
    """Sample within a run."""
    
    __tablename__ = "samples"
    
    # Required metadata
    sample_id: Mapped[str] = mapped_column(String(100), nullable=False)
    collection_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    host: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    sequencing_run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Optional metadata
    clinical_group: Mapped[Optional[str]] = mapped_column(String(100))
    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    control_type: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Status
    status: Mapped[SampleStatus] = mapped_column(
        Enum(SampleStatus),
        default=SampleStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Input files
    r1_path: Mapped[str] = mapped_column(String(500), nullable=False)
    r2_path: Mapped[Optional[str]] = mapped_column(String(500))
    r1_checksum: Mapped[Optional[str]] = mapped_column(String(64))
    r2_checksum: Mapped[Optional[str]] = mapped_column(String(64))
    
    # Additional metadata stored as JSON
    metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    
    # Foreign key
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Relationships
    run: Mapped["Run"] = relationship(back_populates="samples")
    qc_metrics: Mapped[Optional["QCMetrics"]] = relationship(
        back_populates="sample",
        uselist=False,
        cascade="all, delete-orphan",
    )
    consensus: Mapped[Optional["Consensus"]] = relationship(
        back_populates="sample",
        uselist=False,
        cascade="all, delete-orphan",
    )
    variants: Mapped[list["Variant"]] = relationship(
        back_populates="sample",
        cascade="all, delete-orphan",
    )
    lineage: Mapped[Optional["LineageAssignment"]] = relationship(
        back_populates="sample",
        uselist=False,
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        Index("ix_samples_run", "run_id"),
        Index("ix_samples_sample_id", "sample_id"),
        Index("ix_samples_status", "status"),
    )


# =============================================================================
# RESULTS MODELS
# =============================================================================

class QCMetrics(Base, UUIDMixin, TimestampMixin):
    """QC metrics for a sample."""
    
    __tablename__ = "qc_metrics"
    
    # Raw reads
    raw_reads: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_bases: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # After trimming
    trimmed_reads: Mapped[int] = mapped_column(Integer, nullable=False)
    trimmed_bases: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Quality metrics
    q20_rate: Mapped[float] = mapped_column(Float, nullable=False)
    q30_rate: Mapped[float] = mapped_column(Float, nullable=False)
    gc_content: Mapped[float] = mapped_column(Float, nullable=False)
    duplication_rate: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Host removal
    host_reads: Mapped[int] = mapped_column(Integer, default=0)
    host_removal_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Mapping
    mapped_reads: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_rate: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Coverage
    mean_depth: Mapped[float] = mapped_column(Float, nullable=False)
    median_depth: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_1x: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_10x: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_30x: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_100x: Mapped[float] = mapped_column(Float, nullable=False)
    
    # QC flags
    qc_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    qc_flags: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    
    # Foreign key
    sample_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("samples.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    # Relationships
    sample: Mapped["Sample"] = relationship(back_populates="qc_metrics")


class Consensus(Base, UUIDMixin, TimestampMixin):
    """Consensus sequence for a sample."""
    
    __tablename__ = "consensus_sequences"
    
    # Sequence info
    sequence_length: Mapped[int] = mapped_column(Integer, nullable=False)
    n_count: Mapped[int] = mapped_column(Integer, nullable=False)
    n_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    ambiguous_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # File references
    fasta_path: Mapped[str] = mapped_column(String(500), nullable=False)
    fasta_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Generation parameters
    min_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    min_allele_freq: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Foreign key
    sample_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("samples.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    # Relationships
    sample: Mapped["Sample"] = relationship(back_populates="consensus")


class Variant(Base, UUIDMixin, TimestampMixin):
    """Called variant for a sample."""
    
    __tablename__ = "variants"
    
    # Position
    chrom: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    ref: Mapped[str] = mapped_column(String(1000), nullable=False)
    alt: Mapped[str] = mapped_column(String(1000), nullable=False)
    
    # Metrics
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    allele_freq: Mapped[float] = mapped_column(Float, nullable=False)
    strand_bias_pvalue: Mapped[Optional[float]] = mapped_column(Float)
    base_quality: Mapped[Optional[float]] = mapped_column(Float)
    
    # Annotation
    gene: Mapped[Optional[str]] = mapped_column(String(100))
    codon_pos: Mapped[Optional[int]] = mapped_column(Integer)
    ref_aa: Mapped[Optional[str]] = mapped_column(String(10))
    alt_aa: Mapped[Optional[str]] = mapped_column(String(10))
    aa_change: Mapped[Optional[str]] = mapped_column(String(50))
    effect: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Classification
    is_consensus: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_minor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Filter
    filter_status: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Foreign key
    sample_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("samples.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Relationships
    sample: Mapped["Sample"] = relationship(back_populates="variants")
    
    __table_args__ = (
        Index("ix_variants_sample", "sample_id"),
        Index("ix_variants_position", "chrom", "pos"),
        Index("ix_variants_gene", "gene"),
    )


class LineageAssignment(Base, UUIDMixin, TimestampMixin):
    """Lineage assignment for a sample."""
    
    __tablename__ = "lineage_assignments"
    
    # Pangolin
    pangolin_lineage: Mapped[Optional[str]] = mapped_column(String(100))
    pangolin_version: Mapped[Optional[str]] = mapped_column(String(50))
    pangolin_db_version: Mapped[Optional[str]] = mapped_column(String(50))
    pangolin_conflict: Mapped[Optional[float]] = mapped_column(Float)
    pangolin_ambiguity: Mapped[Optional[float]] = mapped_column(Float)
    pangolin_scorpio: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Nextclade
    nextclade_clade: Mapped[Optional[str]] = mapped_column(String(100))
    nextclade_version: Mapped[Optional[str]] = mapped_column(String(50))
    nextclade_qc_score: Mapped[Optional[float]] = mapped_column(Float)
    nextclade_qc_status: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Generic clade (for influenza, etc.)
    clade: Mapped[Optional[str]] = mapped_column(String(100))
    clade_method: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Confidence
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    
    # Foreign key
    sample_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("samples.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    # Relationships
    sample: Mapped["Sample"] = relationship(back_populates="lineage")


# =============================================================================
# REFERENCE & DATABASE MANAGEMENT
# =============================================================================

class ReferenceDatabase(Base, UUIDMixin, TimestampMixin):
    """Reference database version tracking."""
    
    __tablename__ = "reference_databases"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Update tracking
    updated_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    update_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    __table_args__ = (
        Index("ix_refdb_name_version", "name", "version", unique=True),
    )


# =============================================================================
# AUDIT LOG
# =============================================================================

class AuditLog(Base, UUIDMixin):
    """Audit log for security and compliance."""
    
    __tablename__ = "audit_logs"
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100))
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Foreign key (nullable for system events)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
    
    __table_args__ = (
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_user", "user_id"),
        Index("ix_audit_action", "action"),
    )
