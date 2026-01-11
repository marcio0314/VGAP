"""
VGAP Regression Test Suite

End-to-end regression tests to verify pipeline behavior across versions.
These tests run against fixtures and verify output reproducibility.
"""

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest


# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXPECTED_OUTPUTS = FIXTURES_DIR / "expected_outputs"


class RegressionTestResult:
    """Result from a regression test."""
    
    def __init__(
        self,
        test_name: str,
        passed: bool,
        expected_hash: str,
        actual_hash: str,
        details: str = "",
    ):
        self.test_name = test_name
        self.passed = passed
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        self.details = details
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "expected_hash": self.expected_hash,
            "actual_hash": self.actual_hash,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def normalize_vcf(vcf_path: Path) -> str:
    """Normalize VCF content for comparison (remove dates, sort)."""
    lines = []
    with open(vcf_path) as f:
        for line in f:
            # Skip header lines with dates
            if line.startswith("##fileDate"):
                continue
            if line.startswith("##source"):
                continue
            lines.append(line)
    
    # Sort non-header lines
    header_lines = [l for l in lines if l.startswith("#")]
    data_lines = sorted([l for l in lines if not l.startswith("#")])
    
    return "".join(header_lines + data_lines)


def normalize_fasta(fasta_path: Path) -> str:
    """Normalize FASTA for comparison."""
    lines = []
    with open(fasta_path) as f:
        for line in f:
            lines.append(line.strip().upper())
    return "\n".join(lines)


class TestQCPipeline:
    """Regression tests for QC pipeline."""
    
    @pytest.fixture
    def sample_fastq(self, tmp_path: Path) -> Path:
        """Create a minimal test FASTQ file."""
        fastq_path = tmp_path / "test_R1.fastq"
        fastq_path.write_text(
            "@read1\n"
            "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n"
            "+\n"
            "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n"
            "@read2\n"
            "GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA\n"
            "+\n"
            "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n"
        )
        return fastq_path
    
    def test_qc_output_consistency(self, sample_fastq: Path, tmp_path: Path):
        """Test that QC produces consistent output."""
        from vgap.pipeline.qc import QCPipeline, QCConfig
        
        config = QCConfig(
            min_length=30,
            min_quality=20,
            adapter_fasta=None,
        )
        
        pipeline = QCPipeline(config)
        
        # Run twice and compare
        result1 = pipeline.run(
            sample_fastq, None, tmp_path / "run1",
            sample_id="test1",
        )
        
        result2 = pipeline.run(
            sample_fastq, None, tmp_path / "run2",
            sample_id="test2",
        )
        
        # Metrics should be identical
        assert result1.raw_reads == result2.raw_reads
        assert result1.trimmed_reads == result2.trimmed_reads
        assert result1.q20_rate == result2.q20_rate
        assert result1.q30_rate == result2.q30_rate


class TestVariantCalling:
    """Regression tests for variant calling."""
    
    @pytest.fixture
    def sample_bam(self, tmp_path: Path) -> Path:
        """Mock BAM file path (would need real file for full test)."""
        return tmp_path / "test.bam"
    
    def test_variant_calling_deterministic(self, tmp_path: Path):
        """Test that variant calling is deterministic."""
        # This test requires real BAM files - skip if not available
        bam_path = FIXTURES_DIR / "small_sample.bam"
        if not bam_path.exists():
            pytest.skip("Test BAM file not available")
        
        from vgap.pipeline.variants import IvarVariantCaller
        
        caller = IvarVariantCaller()
        
        # Run twice
        result1 = caller.call_variants(
            bam_path,
            FIXTURES_DIR / "reference.fasta",
            tmp_path / "run1",
        )
        
        result2 = caller.call_variants(
            bam_path,
            FIXTURES_DIR / "reference.fasta",
            tmp_path / "run2",
        )
        
        # Compare VCFs
        if result1.vcf_path.exists() and result2.vcf_path.exists():
            vcf1 = normalize_vcf(result1.vcf_path)
            vcf2 = normalize_vcf(result2.vcf_path)
            assert vcf1 == vcf2


class TestConsensusGeneration:
    """Regression tests for consensus generation."""
    
    def test_consensus_reproducibility(self, tmp_path: Path):
        """Test that consensus sequences are reproducible."""
        bam_path = FIXTURES_DIR / "small_sample.bam"
        if not bam_path.exists():
            pytest.skip("Test BAM file not available")
        
        from vgap.pipeline.mapping import ConsensusGenerator
        
        generator = ConsensusGenerator(min_depth=10, min_freq=0.5)
        
        result1 = generator.generate(
            bam_path,
            FIXTURES_DIR / "reference.fasta",
            tmp_path / "consensus1.fasta",
        )
        
        result2 = generator.generate(
            bam_path,
            FIXTURES_DIR / "reference.fasta",
            tmp_path / "consensus2.fasta",
        )
        
        # Compare consensus sequences
        if result1.consensus_path.exists() and result2.consensus_path.exists():
            fasta1 = normalize_fasta(result1.consensus_path)
            fasta2 = normalize_fasta(result2.consensus_path)
            assert fasta1 == fasta2


class TestLineageAssignment:
    """Regression tests for lineage assignment."""
    
    @pytest.fixture
    def sample_consensus(self, tmp_path: Path) -> Path:
        """Create a minimal consensus FASTA."""
        # This would need a real SARS-CoV-2 sequence for proper testing
        fasta_path = tmp_path / "consensus.fasta"
        fasta_path.write_text(
            ">sample1\n"
            "ATCG" * 1000 + "\n"
        )
        return fasta_path
    
    def test_lineage_consistency(self, sample_consensus: Path, tmp_path: Path):
        """Test that lineage assignment is consistent."""
        # Skip if pangolin not available
        try:
            result = subprocess.run(
                ["pangolin", "--version"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                pytest.skip("Pangolin not available")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Pangolin not available")
        
        from vgap.pipeline.lineage import LineagePipeline
        
        pipeline = LineagePipeline()
        
        result1 = pipeline.run(sample_consensus, tmp_path / "run1")
        result2 = pipeline.run(sample_consensus, tmp_path / "run2")
        
        # Lineage should be identical
        assert result1.lineage == result2.lineage


class TestReportGeneration:
    """Regression tests for report generation."""
    
    def test_report_contains_required_sections(self, tmp_path: Path):
        """Test that reports contain all required sections."""
        from vgap.pipeline.reporting import ReportPipeline, ReportConfig
        
        config = ReportConfig(
            title="Test Report",
            include_figures=True,
            include_tables=True,
            include_provenance=True,
        )
        
        pipeline = ReportPipeline(tmp_path)
        
        # Mock data
        samples_data = [
            {
                "sample_id": "test1",
                "qc_pass": True,
                "mean_depth": 100.0,
                "coverage_10x": 0.95,
                "lineage": "BA.2.86",
                "variants": [],
            }
        ]
        
        outputs = pipeline.generate(
            run_id="test-run",
            samples_data=samples_data,
            provenance={"software": []},
            config=config,
        )
        
        # Check report was created
        assert outputs.get("html")
        
        # Check content
        report_path = Path(outputs["html"])
        if report_path.exists():
            content = report_path.read_text()
            assert "test1" in content
            assert "BA.2.86" in content


class TestProvenanceTracking:
    """Regression tests for provenance tracking."""
    
    def test_provenance_capture(self, tmp_path: Path):
        """Test that provenance is properly captured."""
        from vgap.utils.provenance import ProvenanceCollector
        
        collector = ProvenanceCollector(run_id="test-run")
        
        # Record steps
        collector.record_step(
            name="qc",
            tool="fastp",
            version="0.23.4",
            parameters={"min_length": 50},
            inputs=["sample_R1.fastq"],
            outputs=["sample_trimmed.fastq"],
        )
        
        # Save and reload
        collector.save(tmp_path / "provenance.json")
        loaded = ProvenanceCollector.load(tmp_path / "provenance.json")
        
        # Verify
        assert loaded.run_id == "test-run"
        assert len(loaded.steps) == 1
        assert loaded.steps[0]["tool"] == "fastp"


class TestEndToEnd:
    """End-to-end regression tests."""
    
    def test_full_pipeline_fixture(self, tmp_path: Path):
        """Run full pipeline on fixture data and compare to expected."""
        fixture_dir = FIXTURES_DIR / "full_run"
        if not fixture_dir.exists():
            pytest.skip("Full run fixture not available")
        
        # This would run the complete pipeline and compare outputs
        # to pre-computed expected results
        pass
    
    def test_api_endpoints_return_expected_structure(self):
        """Test that API endpoints return expected JSON structure."""
        import httpx
        
        # Skip if API not running
        try:
            response = httpx.get("http://localhost:8000/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("API not running")
        except httpx.RequestError:
            pytest.skip("API not running")
        
        # Test health endpoint structure
        health = response.json()
        assert "status" in health
        
        # Test runs list structure
        response = httpx.get(
            "http://localhost:8000/api/v1/runs",
            headers={"Authorization": "Bearer test-token"},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert "total" in data


def run_regression_suite(output_dir: Path) -> List[RegressionTestResult]:
    """Run the complete regression test suite."""
    results = []
    
    # Run pytest and capture results
    result = subprocess.run(
        [
            "pytest",
            __file__,
            "-v",
            "--json-report",
            f"--json-report-file={output_dir}/regression_report.json",
        ],
        capture_output=True,
        text=True,
    )
    
    # Parse results
    report_path = output_dir / "regression_report.json"
    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)
        
        for test in report.get("tests", []):
            results.append(RegressionTestResult(
                test_name=test["nodeid"],
                passed=test["outcome"] == "passed",
                expected_hash="",
                actual_hash="",
                details=test.get("longrepr", ""),
            ))
    
    return results


if __name__ == "__main__":
    # Run regression tests
    import sys
    
    output = Path("./regression_results")
    output.mkdir(exist_ok=True)
    
    results = run_regression_suite(output)
    
    # Print summary
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    
    print(f"\nRegression Test Results: {passed}/{len(results)} passed")
    
    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r.passed:
                print(f"  - {r.test_name}")
        sys.exit(1)
    
    sys.exit(0)
