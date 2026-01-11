"""
VGAP Test Configuration
"""

import pytest
from pathlib import Path


@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory for tests."""
    output = tmp_path / "output"
    output.mkdir()
    return output


@pytest.fixture
def sample_fastq_r1(test_data_dir, tmp_path):
    """Create a sample R1 FASTQ file."""
    fastq = tmp_path / "sample_R1.fastq"
    fastq.write_text(
        "@read1\n"
        "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n"
        "+\n"
        "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n"
        "@read2\n"
        "GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA\n"
        "+\n"
        "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n"
    )
    return fastq


@pytest.fixture
def sample_fastq_r2(test_data_dir, tmp_path):
    """Create a sample R2 FASTQ file."""
    fastq = tmp_path / "sample_R2.fastq"
    fastq.write_text(
        "@read1\n"
        "CGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGAT\n"
        "+\n"
        "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n"
        "@read2\n"
        "TAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC\n"
        "+\n"
        "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n"
    )
    return fastq


@pytest.fixture
def sample_metadata():
    """Sample metadata dictionary."""
    return {
        "sample_id": "TEST001",
        "collection_date": "2024-01-15",
        "host": "human",
        "location": "US",
        "protocol": "amplicon",
        "platform": "Illumina NovaSeq",
        "run_id": "RUN001",
        "batch_id": "BATCH001",
    }
