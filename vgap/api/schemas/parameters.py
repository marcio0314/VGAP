from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel, Field, field_validator, model_validator

class PipelineMode(str, Enum):
    SHOTGUN = "shotgun"
    AMPLICON = "amplicon"
    # Legacy aliases
    ILLUMINA = "illumina" 
    NANOPORE = "nanopore"

class VirusTarget(str, Enum):
    SARS_COV_2 = "sars_cov_2"
    INFLUENZA_A = "influenza_a"
    INFLUENZA_B = "influenza_b"
    RSV = "rsv"
    GENERIC_RNA = "generic_rna"
    GENERIC_DNA = "generic_dna"

class RunParameters(BaseModel):
    # Core Context
    mode: PipelineMode = PipelineMode.SHOTGUN
    virus_target: VirusTarget = VirusTarget.SARS_COV_2
    reference_set: str = "sars-cov-2" # Maps to ReferenceManager key
    primer_scheme: Optional[str] = None # Required for Amplicon mode

    # Mapping Settings
    mapper_preset: str = "sr" # sr (short-read), map-ont (nanopore)
    min_depth: int = Field(default=10, ge=1)
    min_allele_freq: float = Field(default=0.05, ge=0.0, le=1.0, validation_alias="min_af")
    
    # Consensus
    consensus_min_coverage: int = 10
    consensus_min_af: float = 0.5
    
    # Amplicon Specific
    primer_trimming: bool = True
    
    # Segmented Virus Specific
    per_segment_coverage_required: Optional[Dict[str, float]] = None

    @model_validator(mode='after')
    def check_primer_scheme_for_amplicon(self):
        # Allow checking legacy "illumina"/"nanopore" which imply shotgun usually unless stated
        if self.mode == PipelineMode.AMPLICON and not self.primer_scheme:
             raise ValueError("primer_scheme is required for Amplicon mode")
        return self
    
    @model_validator(mode='after')
    def check_virus_defaults(self):
        # Auto-set defaults if not provided but target is known? 
        # For now, we trust the input values, but we could enforce known logical constraints here.
        return self
