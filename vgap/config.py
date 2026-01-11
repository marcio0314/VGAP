"""
VGAP Configuration Management

Centralized configuration using Pydantic Settings with environment variable support.
All configuration is validated at startup and immutable during runtime.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class PipelineMode(str, Enum):
    """Analysis pipeline mode."""
    AMPLICON = "amplicon"
    SHOTGUN = "shotgun"
    AUTO = "auto"


class LogLevel(str, Enum):
    """Logging level."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    model_config = SettingsConfigDict(env_prefix="DATABASE_")
    
    url: PostgresDsn = Field(
        default="postgresql+asyncpg://vgap:vgap@localhost:5432/vgap",
        description="Async database connection URL"
    )
    sync_url: Optional[PostgresDsn] = Field(
        default=None,
        description="Sync database connection URL for migrations"
    )
    pool_size: int = Field(default=5, ge=1, le=50)
    max_overflow: int = Field(default=10, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=5)
    echo: bool = Field(default=False, description="Log SQL queries")


class RedisSettings(BaseSettings):
    """Redis configuration."""
    
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    max_connections: int = Field(default=10, ge=1, le=100)


class CelerySettings(BaseSettings):
    """Celery task queue configuration."""
    
    model_config = SettingsConfigDict(env_prefix="CELERY_")
    
    broker_url: str = Field(default="redis://localhost:6379/0")
    result_backend: str = Field(default="redis://localhost:6379/1")
    task_serializer: str = Field(default="json")
    result_serializer: str = Field(default="json")
    accept_content: list[str] = Field(default=["json"])
    timezone: str = Field(default="UTC")
    enable_utc: bool = Field(default=True)
    task_track_started: bool = Field(default=True)
    task_time_limit: int = Field(default=3600 * 12, description="12 hour limit")
    worker_prefetch_multiplier: int = Field(default=1)
    worker_concurrency: int = Field(default=4)


class SecuritySettings(BaseSettings):
    """Security configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        min_length=32
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60 * 24, ge=5)  # 24 hours
    bcrypt_rounds: int = Field(default=12, ge=4, le=31)
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """Warn if using default secret key in non-dev environment."""
        if "dev-secret-key" in v:
            import warnings
            warnings.warn(
                "Using default SECRET_KEY. Set a secure key in production!",
                UserWarning
            )
        return v


class StorageSettings(BaseSettings):
    """File storage configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    data_dir: Path = Field(default=Path("/data"))
    upload_dir: Path = Field(default=Path("/data/uploads"))
    results_dir: Path = Field(default=Path("/data/results"))
    references_dir: Path = Field(default=Path("/data/references"))
    temp_dir: Path = Field(default=Path("/data/temp"))
    
    max_upload_size_gb: float = Field(default=20.0, ge=1.0, le=100.0)
    
    def ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        for path in [
            self.data_dir,
            self.upload_dir,
            self.results_dir,
            self.references_dir,
            self.temp_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


class PipelineSettings(BaseSettings):
    """Pipeline execution configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    # Consensus generation
    min_depth: int = Field(default=10, ge=1, le=1000)
    min_allele_freq: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Variant calling
    min_variant_depth: int = Field(default=10, ge=1, le=1000)
    min_variant_freq: float = Field(default=0.02, ge=0.0, le=1.0)
    strand_bias_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    
    # Quality control
    min_read_length: int = Field(default=50, ge=20, le=500)
    min_base_quality: int = Field(default=20, ge=0, le=40)
    
    # Contamination thresholds
    negative_control_threshold: float = Field(default=0.001, ge=0.0, le=0.1)
    
    # Coverage thresholds for reporting
    coverage_thresholds: list[int] = Field(default=[1, 10, 30, 100])


class LineageSettings(BaseSettings):
    """Lineage database configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    pangolin_data_path: Path = Field(default=Path("/data/references/pangolin"))
    nextclade_data_path: Path = Field(default=Path("/data/references/nextclade"))
    
    # Auto-update settings (admin controlled)
    auto_update_enabled: bool = Field(default=False)
    update_check_interval_hours: int = Field(default=24)


class MonitoringSettings(BaseSettings):
    """Monitoring and logging configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)
    
    log_level: LogLevel = Field(default=LogLevel.INFO)
    log_format: str = Field(default="json")
    
    # Audit logging
    audit_log_enabled: bool = Field(default=True)
    audit_log_retention_days: int = Field(default=365)


class ResourceSettings(BaseSettings):
    """Resource limits configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    max_concurrent_runs: int = Field(default=4, ge=1, le=100)
    worker_memory_limit_mb: int = Field(default=16384, ge=1024)
    worker_cpu_limit: int = Field(default=4, ge=1, le=128)
    
    # Data retention
    data_retention_days: int = Field(default=730)  # 2 years
    archive_enabled: bool = Field(default=True)


class Settings(BaseSettings):
    """
    Main application settings.
    
    All settings are loaded from environment variables with sensible defaults.
    Use .env file for local development.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = Field(default="VGAP")
    app_version: str = Field(default="0.1.0")
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)
    
    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=4)
    api_prefix: str = Field(default="/api/v1")
    
    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    lineage: LineageSettings = Field(default_factory=LineageSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    resources: ResourceSettings = Field(default_factory=ResourceSettings)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Settings are loaded once and cached for the lifetime of the application.
    """
    return Settings()


# Convenience alias
settings = get_settings()
