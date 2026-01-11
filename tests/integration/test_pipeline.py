"""
VGAP Integration Tests
"""

import pytest
from pathlib import Path

from tests.fixtures import create_test_fixtures


@pytest.fixture(scope="module")
def test_fixtures(tmp_path_factory):
    """Create test fixtures for integration tests."""
    fixture_dir = tmp_path_factory.mktemp("fixtures")
    return create_test_fixtures(fixture_dir)


class TestPreflightIntegration:
    """Integration tests for pre-flight validation."""
    
    def test_full_validation_pipeline(self, test_fixtures):
        """Test complete validation on synthetic data."""
        from vgap.validators.preflight import PreflightValidator
        
        validator = PreflightValidator()
        
        samples = [{
            "r1_path": str(test_fixtures["r1"]),
            "r2_path": str(test_fixtures["r2"]),
            "metadata": {
                "sample_id": "TEST001",
                "collection_date": "2024-01-15",
                "host": "human",
                "location": "US",
                "protocol": "amplicon",
                "platform": "Illumina NovaSeq",
                "run_id": "RUN001",
                "batch_id": "BATCH001",
            }
        }]
        
        result = validator.validate_run(
            samples=samples,
            mode="amplicon",
            primer_scheme="ARTIC_v4",
        )
        
        assert result.passed or result.status.value == "warning"
        assert "sample_count" in result.metadata
        assert result.metadata["sample_count"] == 1


class TestQCIntegration:
    """Integration tests for QC pipeline."""
    
    @pytest.mark.skipif(
        not Path("/usr/bin/fastp").exists(),
        reason="fastp not installed"
    )
    def test_fastp_qc(self, test_fixtures, tmp_path):
        """Test fastp QC on synthetic data."""
        from vgap.pipeline.qc import FastpRunner
        
        runner = FastpRunner()
        
        metrics = runner.run(
            r1_input=test_fixtures["r1"],
            r1_output=tmp_path / "trimmed_R1.fastq.gz",
            r2_input=test_fixtures["r2"],
            r2_output=tmp_path / "trimmed_R2.fastq.gz",
        )
        
        assert metrics.raw_reads > 0
        assert metrics.q20_rate >= 0


class TestReportingIntegration:
    """Integration tests for report generation."""
    
    def test_html_report_generation(self, tmp_path):
        """Test HTML report generation."""
        from vgap.pipeline.reporting import ReportPipeline, ReportConfig
        
        pipeline = ReportPipeline(tmp_path)
        
        samples_data = [{
            "sample_id": "TEST001",
            "qc": {"qc_pass": True, "raw_reads": 1000},
            "coverage": {"mean_depth": 100.0, "coverage_10x": 0.95},
            "variants": [{"pos": 100, "ref": "A", "alt": "G"}],
            "lineage": {"pangolin_lineage": "BA.2.86"},
        }]
        
        outputs = pipeline.generate(
            run_id="test-run-001",
            samples_data=samples_data,
            config=ReportConfig(title="Test Report"),
        )
        
        assert "html" in outputs
        assert outputs["html"].exists()
        
        # Check HTML content
        content = outputs["html"].read_text()
        assert "TEST001" in content
        assert "BA.2.86" in content


class TestProvenanceIntegration:
    """Integration tests for provenance tracking."""
    
    def test_full_provenance_workflow(self, test_fixtures, tmp_path):
        """Test complete provenance collection and verification."""
        from vgap.utils.provenance import (
            ProvenanceCollector,
            generate_checksums_file,
            verify_checksums,
        )
        
        # Create provenance
        provenance = ProvenanceCollector()
        provenance.user_id = "test-user"
        provenance.parameters = {"min_depth": 10, "min_af": 0.5}
        
        # Add input file
        provenance.add_input_file(test_fixtures["r1"])
        provenance.add_input_file(test_fixtures["r2"])
        
        # Add software
        provenance.add_software("fastp", "0.23.4")
        provenance.add_software("minimap2", "2.26")
        
        # Add seeds
        provenance.set_seed("iqtree", 12345)
        
        # Create some output files
        output1 = tmp_path / "consensus.fa"
        output1.write_text(">TEST001\nATCG\n")
        
        provenance.add_output_file(output1)
        
        # Set validation
        provenance.set_validation("preflight", "PASS")
        provenance.set_validation("qc", "PASS")
        
        # Save
        prov_path = tmp_path / "provenance.json"
        provenance.save(prov_path)
        
        # Generate checksums
        generate_checksums_file(tmp_path)
        
        # Verify checksums
        valid, errors = verify_checksums(tmp_path)
        
        assert valid
        assert len(errors) == 0
        
        # Load and verify
        loaded = ProvenanceCollector.load(prov_path)
        assert loaded.run_id == provenance.run_id
        assert loaded.parameters["min_depth"] == 10
        assert loaded.random_seeds["iqtree"] == 12345


class TestAPIIntegration:
    """Integration tests for API endpoints."""
    
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from vgap.api.main import app
        return TestClient(app)
    
    def test_full_run_workflow(self, client):
        """Test complete run creation and status workflow."""
        # Login
        login_response = client.post("/api/v1/auth/login", json={
            "email": "admin@vgap.local",
            "password": "admin_dev_password"
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create run
        run_response = client.post("/api/v1/runs", headers=headers, json={
            "name": "Integration Test Run",
            "mode": "amplicon",
            "primer_scheme": "ARTIC_v4",
            "samples": [{
                "metadata": {
                    "sample_id": "INTTEST001",
                    "collection_date": "2024-01-15",
                    "host": "human",
                    "location": "US",
                    "protocol": "amplicon",
                    "platform": "Illumina",
                    "run_id": "RUN001",
                    "batch_id": "BATCH001",
                },
                "r1_filename": "INTTEST001_R1.fastq.gz",
                "r2_filename": "INTTEST001_R2.fastq.gz",
            }]
        })
        
        assert run_response.status_code == 201
        run_data = run_response.json()
        run_id = run_data["id"]
        
        # Get run status
        status_response = client.get(f"/api/v1/runs/{run_id}/status", headers=headers)
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "pending"
        
        # List runs
        list_response = client.get("/api/v1/runs", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 1
