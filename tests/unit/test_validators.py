"""
Tests for pre-flight validation module.
"""

import pytest
from pathlib import Path

from vgap.validators.preflight import (
    FASTQValidator,
    PairedReadValidator,
    MetadataValidator,
    AmpliconValidator,
    PreflightValidator,
    ValidationStatus,
    ValidationErrorCode,
)


class TestFASTQValidator:
    """Tests for FASTQ file validation."""
    
    def test_validate_safe_filename(self):
        validator = FASTQValidator()
        result = validator.validate_filename(Path("sample_R1.fastq.gz"))
        assert result.passed
    
    def test_validate_unsafe_filename(self):
        validator = FASTQValidator()
        result = validator.validate_filename(Path("sample R1.fastq.gz"))
        assert result.blocked
        assert result.errors[0].code == ValidationErrorCode.UNSAFE_FILENAME
    
    def test_validate_file_exists(self, sample_fastq_r1):
        validator = FASTQValidator()
        result = validator.validate_file_exists(sample_fastq_r1)
        assert result.passed
    
    def test_validate_file_not_exists(self):
        validator = FASTQValidator()
        result = validator.validate_file_exists(Path("/nonexistent/file.fastq"))
        assert result.blocked
        assert result.errors[0].code == ValidationErrorCode.FASTQ_NOT_FOUND
    
    def test_validate_fastq_format(self, sample_fastq_r1):
        validator = FASTQValidator()
        result = validator.validate_fastq_format(sample_fastq_r1)
        assert result.passed
        assert "read_count_sampled" in result.metadata
    
    def test_validate_invalid_fastq(self, tmp_path):
        invalid = tmp_path / "invalid.fastq"
        invalid.write_text("Not a FASTQ file\n")
        
        validator = FASTQValidator()
        result = validator.validate_fastq_format(invalid)
        assert result.blocked
    
    def test_validate_empty_file(self, tmp_path):
        empty = tmp_path / "empty.fastq"
        empty.touch()
        
        validator = FASTQValidator()
        result = validator.validate_file_size(empty)
        assert result.blocked
        assert result.errors[0].code == ValidationErrorCode.FASTQ_EMPTY_FILE


class TestPairedReadValidator:
    """Tests for paired-end read validation."""
    
    def test_validate_matching_pairs(self, sample_fastq_r1, sample_fastq_r2):
        validator = PairedReadValidator()
        result = validator.validate_pair_consistency(sample_fastq_r1, sample_fastq_r2)
        assert result.passed
    
    def test_validate_mismatched_ids(self, tmp_path):
        r1 = tmp_path / "R1.fastq"
        r2 = tmp_path / "R2.fastq"
        
        r1.write_text("@read1\nATCG\n+\nIIII\n")
        r2.write_text("@read2\nGCTA\n+\nIIII\n")  # Different ID
        
        validator = PairedReadValidator()
        result = validator.validate_pair_consistency(r1, r2)
        assert result.blocked
        assert result.errors[0].code == ValidationErrorCode.PAIR_ID_MISMATCH


class TestMetadataValidator:
    """Tests for sample metadata validation."""
    
    def test_validate_complete_metadata(self, sample_metadata):
        validator = MetadataValidator()
        result = validator.validate_sample_metadata(sample_metadata)
        assert result.passed
    
    def test_missing_required_field(self, sample_metadata):
        del sample_metadata["collection_date"]
        
        validator = MetadataValidator()
        result = validator.validate_sample_metadata(sample_metadata)
        assert result.blocked
        assert result.errors[0].code == ValidationErrorCode.METADATA_MISSING_FIELD
    
    def test_invalid_date_format(self):
        validator = MetadataValidator()
        result = validator.validate_date_format("01/15/2024")
        assert result.blocked
        assert result.errors[0].code == ValidationErrorCode.METADATA_INVALID_DATE
    
    def test_valid_date_format(self):
        validator = MetadataValidator()
        result = validator.validate_date_format("2024-01-15")
        assert result.passed
    
    def test_invalid_protocol(self):
        validator = MetadataValidator()
        result = validator.validate_protocol("invalid_protocol")
        assert result.blocked


class TestAmpliconValidator:
    """Tests for amplicon-specific validation."""
    
    def test_known_primer_scheme(self):
        validator = AmpliconValidator()
        result = validator.validate_primer_scheme_exists("ARTIC_v4")
        assert result.passed
        assert "scheme_info" in result.metadata
    
    def test_unknown_primer_scheme(self):
        validator = AmpliconValidator()
        result = validator.validate_primer_scheme_exists("UNKNOWN_SCHEME")
        assert result.blocked
        assert result.errors[0].code == ValidationErrorCode.PRIMER_SCHEME_NOT_FOUND
    
    def test_sufficient_overlap(self):
        validator = AmpliconValidator()
        result = validator.validate_overlap_sufficiency(
            read_length=250,
            scheme_name="ARTIC_v4"
        )
        assert result.passed
    
    def test_insufficient_overlap(self):
        validator = AmpliconValidator()
        result = validator.validate_overlap_sufficiency(
            read_length=100,  # Too short
            scheme_name="ARTIC_v4"
        )
        assert result.blocked
        assert result.errors[0].code == ValidationErrorCode.INSUFFICIENT_OVERLAP


class TestPreflightValidator:
    """Integration tests for complete pre-flight validation."""
    
    def test_validate_sample(self, sample_fastq_r1, sample_fastq_r2, sample_metadata):
        validator = PreflightValidator()
        
        result = validator.validate_sample(
            r1_path=sample_fastq_r1,
            r2_path=sample_fastq_r2,
            metadata=sample_metadata,
            mode="amplicon",
            primer_scheme="ARTIC_v4",
        )
        
        assert result.passed or result.status == ValidationStatus.WARNING
    
    def test_amplicon_mode_requires_scheme(self, sample_fastq_r1, sample_metadata):
        validator = PreflightValidator()
        
        result = validator.validate_sample(
            r1_path=sample_fastq_r1,
            r2_path=None,
            metadata=sample_metadata,
            mode="amplicon",
            primer_scheme=None,  # Missing!
        )
        
        assert result.blocked
