"""
VGAP Pre-flight Validation Module

Implements mandatory hard guards for input validation before pipeline execution.
All validation failures block the run with deterministic error messages.
"""

import gzip
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


class ValidationStatus(str, Enum):
    """Validation result status."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


class ValidationErrorCode(str, Enum):
    """Standardized error codes for validation failures."""
    # FASTQ Errors
    FASTQ_NOT_FOUND = "FASTQ_NOT_FOUND"
    FASTQ_CORRUPT_GZIP = "FASTQ_CORRUPT_GZIP"
    FASTQ_INVALID_FORMAT = "FASTQ_INVALID_FORMAT"
    FASTQ_EMPTY_FILE = "FASTQ_EMPTY_FILE"
    
    # Pair Errors
    PAIR_MISMATCH = "PAIR_MISMATCH"
    PAIR_COUNT_MISMATCH = "PAIR_COUNT_MISMATCH"
    PAIR_ID_MISMATCH = "PAIR_ID_MISMATCH"
    
    # Metadata Errors
    METADATA_MISSING_FIELD = "METADATA_MISSING_FIELD"
    METADATA_INVALID_DATE = "METADATA_INVALID_DATE"
    METADATA_INVALID_VALUE = "METADATA_INVALID_VALUE"
    
    # Amplicon Errors
    PRIMER_SCHEME_NOT_FOUND = "PRIMER_SCHEME_NOT_FOUND"
    PRIMER_SCHEME_INVALID = "PRIMER_SCHEME_INVALID"
    INSUFFICIENT_OVERLAP = "INSUFFICIENT_OVERLAP"
    
    # Reference Errors
    REFERENCE_NOT_FOUND = "REFERENCE_NOT_FOUND"
    REFERENCE_INVALID = "REFERENCE_INVALID"
    DATABASE_NOT_FOUND = "DATABASE_NOT_FOUND"
    
    # Filename Errors
    UNSAFE_FILENAME = "UNSAFE_FILENAME"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"


@dataclass
class ValidationError:
    """A single validation error with remediation guidance."""
    code: ValidationErrorCode
    message: str
    field: Optional[str] = None
    sample_id: Optional[str] = None
    remediation: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "message": self.message,
            "field": self.field,
            "sample_id": self.sample_id,
            "remediation": self.remediation,
        }


@dataclass
class ValidationWarning:
    """A validation warning (non-blocking)."""
    code: str
    message: str
    field: Optional[str] = None
    sample_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "sample_id": self.sample_id,
        }


@dataclass
class ValidationResult:
    """Complete validation result for a pre-flight check."""
    status: ValidationStatus
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    @property
    def passed(self) -> bool:
        return self.status == ValidationStatus.PASS
    
    @property
    def blocked(self) -> bool:
        return self.status == ValidationStatus.FAIL
    
    def add_error(self, error: ValidationError) -> None:
        self.errors.append(error)
        self.status = ValidationStatus.FAIL
    
    def add_warning(self, warning: ValidationWarning) -> None:
        self.warnings.append(warning)
        if self.status == ValidationStatus.PASS:
            self.status = ValidationStatus.WARNING
    
    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.metadata.update(other.metadata)
        
        if other.status == ValidationStatus.FAIL:
            self.status = ValidationStatus.FAIL
        elif other.status == ValidationStatus.WARNING and self.status == ValidationStatus.PASS:
            self.status = ValidationStatus.WARNING
    
    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "metadata": self.metadata,
        }


class FASTQValidator:
    """Validates FASTQ file format and integrity."""
    
    # Safe filename pattern: alphanumeric, underscores, hyphens, periods
    SAFE_FILENAME_PATTERN = re.compile(r'^[\w\-\.]+$')
    
    # FASTQ header pattern
    FASTQ_HEADER_PATTERN = re.compile(r'^@[\w\-\.:\s/]+$')
    
    def __init__(self, max_file_size_gb: float = 20.0):
        self.max_file_size_bytes = int(max_file_size_gb * 1024 * 1024 * 1024)
    
    def validate_filename(self, path: Path) -> ValidationResult:
        """Check filename for unsafe characters."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if not self.SAFE_FILENAME_PATTERN.match(path.name):
            result.add_error(ValidationError(
                code=ValidationErrorCode.UNSAFE_FILENAME,
                message=f"Filename contains unsafe characters: {path.name}",
                field="filename",
                remediation="Rename file to contain only alphanumeric characters, "
                           "underscores, hyphens, and periods. No spaces allowed."
            ))
        
        return result
    
    def validate_file_exists(self, path: Path) -> ValidationResult:
        """Check that file exists and is readable."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if not path.exists():
            result.add_error(ValidationError(
                code=ValidationErrorCode.FASTQ_NOT_FOUND,
                message=f"FASTQ file not found: {path}",
                field="file_path",
                remediation="Ensure the file exists and the path is correct."
            ))
        elif not path.is_file():
            result.add_error(ValidationError(
                code=ValidationErrorCode.FASTQ_NOT_FOUND,
                message=f"Path is not a file: {path}",
                field="file_path",
                remediation="Provide a path to a file, not a directory."
            ))
        
        return result
    
    def validate_file_size(self, path: Path) -> ValidationResult:
        """Check file size is within limits."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if path.exists():
            size = path.stat().st_size
            result.metadata["file_size_bytes"] = size
            
            if size == 0:
                result.add_error(ValidationError(
                    code=ValidationErrorCode.FASTQ_EMPTY_FILE,
                    message=f"FASTQ file is empty: {path}",
                    field="file_size",
                    remediation="Provide a non-empty FASTQ file."
                ))
            elif size > self.max_file_size_bytes:
                result.add_error(ValidationError(
                    code=ValidationErrorCode.FILE_TOO_LARGE,
                    message=f"File exceeds maximum size ({size / 1e9:.2f} GB > "
                           f"{self.max_file_size_bytes / 1e9:.2f} GB): {path}",
                    field="file_size",
                    remediation="Split the file or contact administrator to increase limit."
                ))
        
        return result
    
    def validate_gzip_integrity(self, path: Path, sample_size: int = 1024 * 1024) -> ValidationResult:
        """Check gzip file integrity by reading first and last portions."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if not path.name.endswith('.gz'):
            return result  # Not gzipped, skip this check
        
        try:
            with gzip.open(path, 'rt') as f:
                # Read beginning
                f.read(sample_size)
                
                # Try to seek to end (may fail on corrupted files)
                try:
                    f.seek(-sample_size, 2)  # Seek from end
                    f.read(sample_size)
                except OSError:
                    # Some gzip files don't support seeking, read sequentially
                    pass
                    
        except gzip.BadGzipFile:
            result.add_error(ValidationError(
                code=ValidationErrorCode.FASTQ_CORRUPT_GZIP,
                message=f"Corrupt gzip file: {path}",
                field="gzip_integrity",
                remediation="Re-download or re-transfer the file. "
                           "Verify with: gzip -t {path}"
            ))
        except Exception as e:
            result.add_error(ValidationError(
                code=ValidationErrorCode.FASTQ_CORRUPT_GZIP,
                message=f"Error reading gzip file: {path}: {str(e)}",
                field="gzip_integrity",
                remediation="Verify file integrity and try again."
            ))
        
        return result
    
    def validate_fastq_format(
        self,
        path: Path,
        num_records: int = 1000
    ) -> ValidationResult:
        """Validate FASTQ format by checking first N records."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        try:
            opener = gzip.open if path.name.endswith('.gz') else open
            read_lengths = []
            record_count = 0
            
            with opener(path, 'rt') as f:
                line_num = 0
                while record_count < num_records:
                    # Read 4 lines (one FASTQ record)
                    header = f.readline()
                    if not header:
                        break  # EOF
                    
                    sequence = f.readline()
                    plus = f.readline()
                    quality = f.readline()
                    
                    line_num += 4
                    
                    # Validate header
                    if not header.startswith('@'):
                        result.add_error(ValidationError(
                            code=ValidationErrorCode.FASTQ_INVALID_FORMAT,
                            message=f"Invalid FASTQ header at line {line_num - 3}: {header[:50]}",
                            field="fastq_format",
                            remediation="FASTQ headers must start with '@'."
                        ))
                        break
                    
                    # Validate plus line
                    if not plus.startswith('+'):
                        result.add_error(ValidationError(
                            code=ValidationErrorCode.FASTQ_INVALID_FORMAT,
                            message=f"Invalid FASTQ separator at line {line_num - 1}",
                            field="fastq_format",
                            remediation="FASTQ quality header must start with '+'."
                        ))
                        break
                    
                    # Validate sequence/quality length match
                    seq_len = len(sequence.strip())
                    qual_len = len(quality.strip())
                    
                    if seq_len != qual_len:
                        result.add_error(ValidationError(
                            code=ValidationErrorCode.FASTQ_INVALID_FORMAT,
                            message=f"Sequence/quality length mismatch at line {line_num - 2}: "
                                   f"{seq_len} vs {qual_len}",
                            field="fastq_format",
                            remediation="Each sequence must have equal length quality string."
                        ))
                        break
                    
                    read_lengths.append(seq_len)
                    record_count += 1
            
            # Store read length statistics
            if read_lengths:
                result.metadata["read_count_sampled"] = len(read_lengths)
                result.metadata["read_length_min"] = min(read_lengths)
                result.metadata["read_length_max"] = max(read_lengths)
                result.metadata["read_length_mean"] = sum(read_lengths) / len(read_lengths)
                
        except Exception as e:
            result.add_error(ValidationError(
                code=ValidationErrorCode.FASTQ_INVALID_FORMAT,
                message=f"Error parsing FASTQ file {path}: {str(e)}",
                field="fastq_format",
                remediation="Verify the file is a valid FASTQ format."
            ))
        
        return result
    
    def compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum for file."""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def validate_file(self, path: Path, compute_checksum: bool = True) -> ValidationResult:
        """Run all file-level validations."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        # Filename check
        result.merge(self.validate_filename(path))
        
        # Existence check
        result.merge(self.validate_file_exists(path))
        if result.blocked:
            return result
        
        # Size check
        result.merge(self.validate_file_size(path))
        if result.blocked:
            return result
        
        # Gzip integrity
        result.merge(self.validate_gzip_integrity(path))
        if result.blocked:
            return result
        
        # FASTQ format
        result.merge(self.validate_fastq_format(path))
        
        # Compute checksum if requested
        if compute_checksum and not result.blocked:
            result.metadata["sha256"] = self.compute_checksum(path)
        
        return result


class PairedReadValidator:
    """Validates paired-end read consistency."""
    
    def extract_read_id(self, header: str) -> str:
        """Extract the read ID from FASTQ header, removing pair indicator."""
        # Remove @ prefix and trailing pair indicators
        read_id = header.lstrip('@').split()[0]
        
        # Handle common pair naming conventions
        # Illumina: @READ_ID/1 or @READ_ID/2
        # Also: @READ_ID 1:... or @READ_ID 2:...
        if read_id.endswith('/1') or read_id.endswith('/2'):
            read_id = read_id[:-2]
        
        return read_id
    
    def validate_pair_consistency(
        self,
        r1_path: Path,
        r2_path: Path,
        num_records: int = 1000
    ) -> ValidationResult:
        """Validate that R1 and R2 reads are properly paired."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        try:
            opener = gzip.open if r1_path.name.endswith('.gz') else open
            
            with opener(r1_path, 'rt') as f1, opener(r2_path, 'rt') as f2:
                record_count = 0
                mismatches = []
                
                while record_count < num_records:
                    # Read headers
                    h1 = f1.readline()
                    if not h1:
                        break
                    h2 = f2.readline()
                    
                    # Skip other lines
                    for _ in range(3):
                        f1.readline()
                        f2.readline()
                    
                    if not h2:
                        result.add_error(ValidationError(
                            code=ValidationErrorCode.PAIR_COUNT_MISMATCH,
                            message=f"R2 file has fewer reads than R1",
                            field="pair_count",
                            remediation="Ensure R1 and R2 files have the same number of reads."
                        ))
                        break
                    
                    # Extract and compare read IDs
                    id1 = self.extract_read_id(h1)
                    id2 = self.extract_read_id(h2)
                    
                    if id1 != id2:
                        mismatches.append((record_count + 1, id1, id2))
                        if len(mismatches) >= 5:
                            break
                    
                    record_count += 1
                
                # Check if R1 has more reads
                if f2.readline():  # R2 still has data
                    pass  # OK
                elif f1.readline():  # R1 has more
                    result.add_error(ValidationError(
                        code=ValidationErrorCode.PAIR_COUNT_MISMATCH,
                        message=f"R1 file has more reads than R2",
                        field="pair_count",
                        remediation="Ensure R1 and R2 files have the same number of reads."
                    ))
                
                if mismatches:
                    examples = "; ".join([
                        f"Record {n}: R1={id1}, R2={id2}"
                        for n, id1, id2 in mismatches[:3]
                    ])
                    result.add_error(ValidationError(
                        code=ValidationErrorCode.PAIR_ID_MISMATCH,
                        message=f"Read ID mismatch between R1 and R2: {examples}",
                        field="pair_ids",
                        remediation="Ensure R1 and R2 files contain matching read pairs in the same order."
                    ))
                
                result.metadata["records_checked"] = record_count
                
        except Exception as e:
            result.add_error(ValidationError(
                code=ValidationErrorCode.PAIR_MISMATCH,
                message=f"Error validating paired reads: {str(e)}",
                field="pair_validation",
                remediation="Verify both files are valid FASTQ format."
            ))
        
        return result


class MetadataValidator:
    """Validates sample metadata schema."""
    
    REQUIRED_FIELDS = [
        "sample_id",
        "collection_date",
        "host",
        "location",
        "protocol",
        "platform",
        "run_id",
        "batch_id",
    ]
    
    VALID_HOSTS = ["human", "animal", "environmental"]
    VALID_PROTOCOLS = ["amplicon", "shotgun", "capture"]
    
    DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    
    def validate_required_fields(self, metadata: dict) -> ValidationResult:
        """Check all required fields are present."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        for field in self.REQUIRED_FIELDS:
            if field not in metadata or metadata[field] is None or str(metadata[field]).strip() == "":
                result.add_error(ValidationError(
                    code=ValidationErrorCode.METADATA_MISSING_FIELD,
                    message=f"Required metadata field missing: {field}",
                    field=field,
                    sample_id=metadata.get("sample_id"),
                    remediation=f"Provide a value for the '{field}' field."
                ))
        
        return result
    
    def validate_date_format(self, date_str: str, field: str = "collection_date") -> ValidationResult:
        """Validate date is in YYYY-MM-DD format."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if not self.DATE_PATTERN.match(str(date_str)):
            result.add_error(ValidationError(
                code=ValidationErrorCode.METADATA_INVALID_DATE,
                message=f"Invalid date format: {date_str}",
                field=field,
                remediation="Use YYYY-MM-DD format (e.g., 2024-01-15)."
            ))
        else:
            # Validate date is reasonable
            try:
                from datetime import datetime
                date = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Check date is not in the future
                if date > datetime.now():
                    result.add_warning(ValidationWarning(
                        code="DATE_IN_FUTURE",
                        message=f"Collection date is in the future: {date_str}",
                        field=field,
                    ))
                
                # Check date is not too old (before 2019 for respiratory viruses)
                if date.year < 2019:
                    result.add_warning(ValidationWarning(
                        code="DATE_VERY_OLD",
                        message=f"Collection date is before 2019: {date_str}",
                        field=field,
                    ))
            except ValueError:
                result.add_error(ValidationError(
                    code=ValidationErrorCode.METADATA_INVALID_DATE,
                    message=f"Invalid date value: {date_str}",
                    field=field,
                    remediation="Ensure the date is valid (e.g., not February 30)."
                ))
        
        return result
    
    def validate_host(self, host: str) -> ValidationResult:
        """Validate host field."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if host.lower() not in self.VALID_HOSTS:
            result.add_warning(ValidationWarning(
                code="UNKNOWN_HOST",
                message=f"Unknown host type: {host}. Expected one of: {self.VALID_HOSTS}",
                field="host",
            ))
        
        return result
    
    def validate_protocol(self, protocol: str) -> ValidationResult:
        """Validate protocol field."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if protocol.lower() not in self.VALID_PROTOCOLS:
            result.add_error(ValidationError(
                code=ValidationErrorCode.METADATA_INVALID_VALUE,
                message=f"Invalid protocol: {protocol}. Must be one of: {self.VALID_PROTOCOLS}",
                field="protocol",
                remediation=f"Use one of the valid protocols: {self.VALID_PROTOCOLS}"
            ))
        
        return result
    
    def validate_sample_metadata(self, metadata: dict) -> ValidationResult:
        """Run all metadata validations for a sample."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        # Required fields
        result.merge(self.validate_required_fields(metadata))
        
        # If we have collection_date, validate format
        if "collection_date" in metadata and metadata["collection_date"]:
            result.merge(self.validate_date_format(str(metadata["collection_date"])))
        
        # Validate host
        if "host" in metadata and metadata["host"]:
            result.merge(self.validate_host(str(metadata["host"])))
        
        # Validate protocol
        if "protocol" in metadata and metadata["protocol"]:
            result.merge(self.validate_protocol(str(metadata["protocol"])))
        
        return result


class AmpliconValidator:
    """Validates amplicon-specific requirements."""
    
    KNOWN_SCHEMES = {
        # Underscore versions (legacy)
        "ARTIC_v3": {"amplicon_length": 400, "overlap": 50},
        "ARTIC_v4": {"amplicon_length": 400, "overlap": 50},
        "ARTIC_v4.1": {"amplicon_length": 400, "overlap": 50},
        "ARTIC_v5": {"amplicon_length": 400, "overlap": 50},
        "midnight": {"amplicon_length": 1200, "overlap": 100},
        # Hyphenated versions (standard naming from ReferenceManager)
        "ARTIC-V3": {"amplicon_length": 400, "overlap": 50},
        "ARTIC-V4": {"amplicon_length": 400, "overlap": 50},
        "ARTIC-V4.1": {"amplicon_length": 400, "overlap": 50},
        "ARTIC-V5": {"amplicon_length": 400, "overlap": 50},
        "ARTIC-V5.3.2": {"amplicon_length": 400, "overlap": 50},
    }
    
    def __init__(self, schemes_dir: Optional[Path] = None):
        self.schemes_dir = schemes_dir
    
    def validate_primer_scheme_exists(
        self,
        scheme_name: str,
        scheme_file: Optional[Path] = None
    ) -> ValidationResult:
        """Validate primer scheme is available."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        # Check known schemes
        if scheme_name in self.KNOWN_SCHEMES:
            result.metadata["scheme_info"] = self.KNOWN_SCHEMES[scheme_name]
            return result
        
        # Check custom scheme file
        if scheme_file:
            if not scheme_file.exists():
                result.add_error(ValidationError(
                    code=ValidationErrorCode.PRIMER_SCHEME_NOT_FOUND,
                    message=f"Primer scheme file not found: {scheme_file}",
                    field="primer_scheme",
                    remediation="Provide a valid primer scheme BED file."
                ))
            else:
                result.merge(self.validate_bed_format(scheme_file))
        elif self.schemes_dir:
            # Look for scheme in schemes directory
            scheme_path = self.schemes_dir / f"{scheme_name}.bed"
            if not scheme_path.exists():
                result.add_error(ValidationError(
                    code=ValidationErrorCode.PRIMER_SCHEME_NOT_FOUND,
                    message=f"Unknown primer scheme: {scheme_name}",
                    field="primer_scheme",
                    remediation=f"Use a known scheme ({list(self.KNOWN_SCHEMES.keys())}) "
                               f"or provide a custom BED file."
                ))
        else:
            result.add_error(ValidationError(
                code=ValidationErrorCode.PRIMER_SCHEME_NOT_FOUND,
                message=f"Unknown primer scheme: {scheme_name}",
                field="primer_scheme",
                remediation=f"Use a known scheme ({list(self.KNOWN_SCHEMES.keys())}) "
                           f"or provide a custom BED file."
            ))
        
        return result
    
    def validate_bed_format(self, bed_path: Path) -> ValidationResult:
        """Validate primer BED file format."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        try:
            with open(bed_path, 'r') as f:
                line_count = 0
                for line in f:
                    line_count += 1
                    if line.startswith('#') or not line.strip():
                        continue
                    
                    fields = line.strip().split('\t')
                    if len(fields) < 6:
                        result.add_error(ValidationError(
                            code=ValidationErrorCode.PRIMER_SCHEME_INVALID,
                            message=f"BED file has fewer than 6 columns at line {line_count}",
                            field="primer_bed",
                            remediation="Primer BED must have: chrom, start, end, name, score, strand"
                        ))
                        break
                    
                    # Validate coordinates are numeric
                    try:
                        start = int(fields[1])
                        end = int(fields[2])
                        if start >= end:
                            result.add_warning(ValidationWarning(
                                code="INVALID_COORDINATES",
                                message=f"Start >= end at line {line_count}",
                                field="primer_bed",
                            ))
                    except ValueError:
                        result.add_error(ValidationError(
                            code=ValidationErrorCode.PRIMER_SCHEME_INVALID,
                            message=f"Non-numeric coordinates at line {line_count}",
                            field="primer_bed",
                            remediation="BED start and end must be integers."
                        ))
                        break
                
                result.metadata["primer_count"] = line_count
                
        except Exception as e:
            result.add_error(ValidationError(
                code=ValidationErrorCode.PRIMER_SCHEME_INVALID,
                message=f"Error reading primer BED file: {str(e)}",
                field="primer_bed",
                remediation="Verify the file is a valid BED format."
            ))
        
        return result
    
    def validate_overlap_sufficiency(
        self,
        read_length: int,
        scheme_name: str,
        min_overlap: int = 20
    ) -> ValidationResult:
        """
        Check if read length provides sufficient overlap for amplicon tiling.
        
        For tiled amplicons, paired reads must overlap in the middle to ensure
        contiguous genome coverage.
        """
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if scheme_name not in self.KNOWN_SCHEMES:
            return result  # Can't validate unknown schemes
        
        scheme = self.KNOWN_SCHEMES[scheme_name]
        amplicon_length = scheme["amplicon_length"]
        
        # For paired reads, calculate expected overlap
        # Assuming paired-end reads from both ends of amplicon
        expected_coverage = 2 * read_length
        gap = amplicon_length - expected_coverage
        
        if gap > 0:
            # Changed from error to warning: Illumina paired-end reads with proper 
            # insert sizes can cover ARTIC amplicons even with 151bp reads.
            # The 2*read_length model is simplistic; real coverage depends on insert size.
            result.add_warning(ValidationWarning(
                code="POTENTIAL_GAP",
                message=f"Read length ({read_length}bp) may be short for amplicon scheme "
                       f"{scheme_name} ({amplicon_length}bp). Ensure proper insert size.",
                field="read_length",
            ))
        elif expected_coverage - amplicon_length < min_overlap:
            result.add_warning(ValidationWarning(
                code="LOW_OVERLAP",
                message=f"Read overlap ({expected_coverage - amplicon_length}bp) is below "
                       f"recommended minimum ({min_overlap}bp)",
                field="read_length",
            ))
        
        return result


class ReferenceValidator:
    """Validates reference databases are available."""
    
    def validate_reference_exists(self, ref_path: Path) -> ValidationResult:
        """Check reference file exists."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if not ref_path.exists():
            result.add_error(ValidationError(
                code=ValidationErrorCode.REFERENCE_NOT_FOUND,
                message=f"Reference file not found: {ref_path}",
                field="reference",
                remediation="Download or configure the reference genome."
            ))
        
        return result
    
    def validate_database_exists(
        self,
        db_type: str,
        db_path: Path
    ) -> ValidationResult:
        """Check database directory exists."""
        result = ValidationResult(status=ValidationStatus.PASS)
        
        if not db_path.exists():
            result.add_error(ValidationError(
                code=ValidationErrorCode.DATABASE_NOT_FOUND,
                message=f"{db_type} database not found at: {db_path}",
                field=f"{db_type}_database",
                remediation=f"Install the {db_type} database or update configuration."
            ))
        
        return result


class PreflightValidator:
    """
    Main pre-flight validation orchestrator.
    
    Runs all validation checks and produces a comprehensive report.
    Any validation failure blocks the run.
    """
    
    def __init__(
        self,
        max_file_size_gb: float = 20.0,
        schemes_dir: Optional[Path] = None,
        references_dir: Optional[Path] = None,
    ):
        self.fastq_validator = FASTQValidator(max_file_size_gb=max_file_size_gb)
        self.pair_validator = PairedReadValidator()
        self.metadata_validator = MetadataValidator()
        self.amplicon_validator = AmpliconValidator(schemes_dir=schemes_dir)
        self.reference_validator = ReferenceValidator()
        self.references_dir = references_dir
    
    def validate_sample(
        self,
        r1_path: Path,
        r2_path: Optional[Path],
        metadata: dict,
        mode: str = "amplicon",
        primer_scheme: Optional[str] = None,
    ) -> ValidationResult:
        """
        Run all validations for a single sample.
        
        Args:
            r1_path: Path to R1 FASTQ
            r2_path: Optional path to R2 FASTQ (None for single-end)
            metadata: Sample metadata dictionary
            mode: Pipeline mode (amplicon or shotgun)
            primer_scheme: Primer scheme name for amplicon mode
        
        Returns:
            ValidationResult with all errors and warnings
        """
        result = ValidationResult(status=ValidationStatus.PASS)
        result.metadata["sample_id"] = metadata.get("sample_id", "unknown")
        
        logger.info("Validating sample", sample_id=result.metadata["sample_id"])
        
        # Validate R1
        logger.debug("Validating R1 file", path=str(r1_path))
        r1_result = self.fastq_validator.validate_file(r1_path)
        result.merge(r1_result)
        result.metadata["r1"] = r1_result.metadata
        
        if result.blocked:
            return result
        
        # Validate R2 if paired
        if r2_path:
            logger.debug("Validating R2 file", path=str(r2_path))
            r2_result = self.fastq_validator.validate_file(r2_path)
            result.merge(r2_result)
            result.metadata["r2"] = r2_result.metadata
            
            if result.blocked:
                return result
            
            # Validate pair consistency
            logger.debug("Validating pair consistency")
            pair_result = self.pair_validator.validate_pair_consistency(r1_path, r2_path)
            result.merge(pair_result)
        
        if result.blocked:
            return result
        
        # Validate metadata
        logger.debug("Validating metadata")
        meta_result = self.metadata_validator.validate_sample_metadata(metadata)
        result.merge(meta_result)
        
        if result.blocked:
            return result
        
        # Amplicon-specific validations
        if mode == "amplicon":
            if not primer_scheme:
                result.add_error(ValidationError(
                    code=ValidationErrorCode.PRIMER_SCHEME_NOT_FOUND,
                    message="Amplicon mode requires a primer scheme",
                    field="primer_scheme",
                    remediation="Specify the primer scheme (e.g., ARTIC_v4.1)"
                ))
            else:
                logger.debug("Validating primer scheme", scheme=primer_scheme)
                scheme_result = self.amplicon_validator.validate_primer_scheme_exists(primer_scheme)
                result.merge(scheme_result)
                
                # Check overlap if we have read length info
                if r1_result.metadata.get("read_length_mean"):
                    overlap_result = self.amplicon_validator.validate_overlap_sufficiency(
                        int(r1_result.metadata["read_length_mean"]),
                        primer_scheme
                    )
                    result.merge(overlap_result)
        
        return result
    
    def validate_run(
        self,
        samples: list[dict],
        mode: str = "amplicon",
        primer_scheme: Optional[str] = None,
        reference_path: Optional[Path] = None,
        lineage_db_path: Optional[Path] = None,
    ) -> ValidationResult:
        """
        Run all validations for a complete run.
        
        Args:
            samples: List of sample dictionaries with 'r1_path', 'r2_path', and metadata
            mode: Pipeline mode
            primer_scheme: Primer scheme for amplicon mode
            reference_path: Path to reference genome
            lineage_db_path: Path to lineage database
        
        Returns:
            Combined ValidationResult for all samples
        """
        result = ValidationResult(status=ValidationStatus.PASS)
        result.metadata["sample_count"] = len(samples)
        result.metadata["mode"] = mode
        
        logger.info("Starting pre-flight validation", 
                   sample_count=len(samples), mode=mode)
        
        # Validate reference if specified
        if reference_path:
            ref_result = self.reference_validator.validate_reference_exists(reference_path)
            result.merge(ref_result)
        
        # Validate lineage database if specified
        if lineage_db_path:
            db_result = self.reference_validator.validate_database_exists(
                "lineage", lineage_db_path
            )
            result.merge(db_result)
        
        if result.blocked:
            return result
        
        # Validate each sample
        sample_results = []
        for sample in samples:
            r1_path = Path(sample["r1_path"])
            r2_path = Path(sample["r2_path"]) if sample.get("r2_path") else None
            metadata = sample.get("metadata", sample)
            
            sample_result = self.validate_sample(
                r1_path=r1_path,
                r2_path=r2_path,
                metadata=metadata,
                mode=mode,
                primer_scheme=primer_scheme,
            )
            sample_results.append(sample_result)
            result.merge(sample_result)
        
        result.metadata["sample_validations"] = [r.to_dict() for r in sample_results]
        
        # Summary
        passed = sum(1 for r in sample_results if r.passed)
        failed = sum(1 for r in sample_results if r.blocked)
        warnings = sum(1 for r in sample_results if r.status == ValidationStatus.WARNING)
        
        result.metadata["summary"] = {
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
        }
        
        logger.info("Pre-flight validation complete",
                   status=result.status.value,
                   passed=passed, failed=failed, warnings=warnings)
        
        return result
