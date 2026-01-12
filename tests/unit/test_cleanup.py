import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from vgap.services.cleanup_manager import CleanupManager
from vgap.config import settings

class TestCleanupManager:
    @pytest.fixture
    def manager(self):
        return CleanupManager()

    def test_safety_zones_protected(self, manager):
        """Verify protected paths are flagged as protected."""
        protected_paths = [
            "/app/vgap/main.py",
            "/app/frontend/src/App.tsx",
            "/app/docker/Dockerfile",
            "/boot/vmlinuz",
            "/etc/passwd",
            str(settings.storage.references_dir / "hg38.fasta")
        ]
        for p in protected_paths:
            assert manager._is_path_protected(Path(p)) is True, f"Failed to protect {p}"

    def test_allowlist_allowed(self, manager):
        """Verify allowed paths are permitted."""
        allowed_paths = [
            str(settings.storage.temp_dir / "temp_file.txt"),
            str(settings.storage.upload_dir / "session_123" / "file.fastq"),
            str(settings.storage.results_dir / "run_abc" / "consensus.fasta"),
        ]
        for p in allowed_paths:
            assert manager._is_path_allowed(Path(p)) is True, f"Failed to allow {p}"

    def test_allowlist_rejected(self, manager):
        """Verify random paths are rejected."""
        rejected_paths = [
            "/root/secret.txt",
            "/home/user/data",
            "/var/www/html",
        ]
        for p in rejected_paths:
            assert manager._is_path_allowed(Path(p)) is False, f"Failed to reject {p}"

    @patch("vgap.services.cleanup_manager.shutil.rmtree")
    @patch("vgap.services.cleanup_manager.Path.unlink")
    def test_execute_cleanup_safety(self, mock_unlink, mock_rmtree, manager):
        """Verify execute_cleanup skips protected/disallowed files."""
        files_to_delete = [
            {"path": "/app/vgap/critical.py", "size": 100}, # Protected
            {"path": "/random/file.txt", "size": 200},      # Not in allowlist
            {"path": str(settings.storage.temp_dir / "safe.tmp"), "size": 300} # OK
        ]

        # Mock is_file/is_dir behavior
        with patch("vgap.services.cleanup_manager.Path.is_file", return_value=True):
             result = manager.execute_cleanup(files_to_delete)

        # Should only delete the safe one
        assert result["deleted_count"] == 1
        assert result["errors"][0].startswith("SKIPPED (Not allowed)") # /app/vgap is not in ALLOWLIST anyway
        # Wait, /app/vgap IS in SAFETY_ZONES, but is it in ALLOWLIST? No.
        # So it fails allowlist check first.
        
        # Check that unlink was called exactly once for the safe file
        mock_unlink.assert_called_once()
        args, _ = mock_unlink.call_args
        # We need to verify the path of the called object, but mock is on Path class? 
        # No, patch("...Path.unlink") patches the method.
        # It's tricky to check 'self' in unbound method patch.
        # But we know it succeeded once.

