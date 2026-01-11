"""
Tests for provenance tracking.
"""

import pytest
from pathlib import Path
from uuid import UUID

from vgap.utils.provenance import (
    ProvenanceCollector,
    generate_checksums_file,
    verify_checksums,
)


class TestProvenanceCollector:
    """Tests for provenance collection."""
    
    def test_create_provenance(self):
        p = ProvenanceCollector()
        assert isinstance(p.run_id, UUID)
        assert p.timestamp is not None
    
    def test_add_software(self):
        p = ProvenanceCollector()
        p.add_software("fastp", "0.23.4")
        
        assert len(p.software) == 1
        assert p.software[0]["name"] == "fastp"
        assert p.software[0]["version"] == "0.23.4"
    
    def test_add_command(self):
        p = ProvenanceCollector()
        p.add_command("fastp", ["fastp", "-i", "input.fq", "-o", "output.fq"])
        
        assert len(p.commands) == 1
        assert "fastp -i input.fq" in p.commands[0]["command"]
    
    def test_add_input_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        p = ProvenanceCollector()
        p.add_input_file(test_file)
        
        assert len(p.inputs["files"]) == 1
        assert p.inputs["files"][0]["sha256"] != ""
    
    def test_to_dict(self):
        p = ProvenanceCollector()
        p.add_software("test", "1.0")
        p.set_seed("iqtree", 12345)
        
        data = p.to_dict()
        
        assert "run_id" in data
        assert "software" in data
        assert data["random_seeds"]["iqtree"] == 12345
    
    def test_save_and_load(self, tmp_path):
        p = ProvenanceCollector()
        p.add_software("test", "1.0")
        p.parameters = {"min_depth": 10}
        
        path = tmp_path / "provenance.json"
        p.save(path)
        
        loaded = ProvenanceCollector.load(path)
        assert loaded.run_id == p.run_id
        assert loaded.software == p.software
        assert loaded.parameters == p.parameters


class TestChecksums:
    """Tests for checksum generation and verification."""
    
    def test_generate_checksums(self, tmp_path):
        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        
        checksums_path = generate_checksums_file(tmp_path)
        
        assert checksums_path.exists()
        content = checksums_path.read_text()
        assert "file1.txt" in content
        assert "file2.txt" in content
    
    def test_verify_checksums_success(self, tmp_path):
        (tmp_path / "file1.txt").write_text("content1")
        generate_checksums_file(tmp_path)
        
        valid, errors = verify_checksums(tmp_path)
        
        assert valid
        assert len(errors) == 0
    
    def test_verify_checksums_missing_file(self, tmp_path):
        (tmp_path / "file1.txt").write_text("content1")
        generate_checksums_file(tmp_path)
        
        # Delete file
        (tmp_path / "file1.txt").unlink()
        
        valid, errors = verify_checksums(tmp_path)
        
        assert not valid
        assert len(errors) == 1
        assert "Missing" in errors[0]
    
    def test_verify_checksums_modified_file(self, tmp_path):
        (tmp_path / "file1.txt").write_text("content1")
        generate_checksums_file(tmp_path)
        
        # Modify file
        (tmp_path / "file1.txt").write_text("modified")
        
        valid, errors = verify_checksums(tmp_path)
        
        assert not valid
        assert len(errors) == 1
        assert "Mismatch" in errors[0]
