"""
VGAP File Upload Service

Handles file uploads with streaming and validation.
"""

import hashlib
import shutil
from pathlib import Path
from typing import AsyncGenerator, Optional
from uuid import uuid4

import aiofiles
import structlog

from vgap.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class UploadService:
    """Handle file uploads with streaming and validation."""
    
    def __init__(self, upload_dir: Optional[Path] = None):
        self.upload_dir = upload_dir or Path(settings.storage.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = settings.storage.max_upload_size_gb * 1024 * 1024 * 1024
    
    def validate_filename(self, filename: str) -> tuple[bool, str]:
        """
        Validate filename is safe.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for unsafe characters
        unsafe_chars = [' ', ';', '&', '|', '$', '`', '(', ')', '{', '}', 
                       '[', ']', '<', '>', '!', '#', '*', '?', '~']
        
        for char in unsafe_chars:
            if char in filename:
                return False, f"Filename contains unsafe character: '{char}'"
        
        # Check for path traversal
        if '..' in filename or filename.startswith('/'):
            return False, "Filename contains path traversal characters"
        
        # Check extension
        valid_extensions = ['.fastq', '.fq', '.fastq.gz', '.fq.gz']
        if not any(filename.lower().endswith(ext) for ext in valid_extensions):
            return False, f"Invalid file extension. Allowed: {valid_extensions}"
        
        return True, ""
    
    async def create_upload_session(self) -> str:
        """
        Create a new upload session.
        
        Returns:
            Session ID for this upload
        """
        session_id = str(uuid4())
        session_dir = self.upload_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Created upload session", session_id=session_id)
        return session_id
    
    async def stream_upload(
        self,
        session_id: str,
        filename: str,
        stream: AsyncGenerator[bytes, None],
    ) -> tuple[Path, str, int]:
        """
        Stream upload a file.
        
        Args:
            session_id: Upload session ID
            filename: Original filename
            stream: Async byte stream
        
        Returns:
            Tuple of (file_path, sha256_checksum, size_bytes)
        """
        # Validate filename
        is_valid, error = self.validate_filename(filename)
        if not is_valid:
            raise ValueError(error)
        
        session_dir = self.upload_dir / session_id
        if not session_dir.exists():
            raise ValueError(f"Invalid session: {session_id}")
        
        file_path = session_dir / filename
        
        sha256 = hashlib.sha256()
        size = 0
        
        async with aiofiles.open(file_path, 'wb') as f:
            async for chunk in stream:
                # Check size limit
                size += len(chunk)
                if size > self.max_size:
                    # Clean up and raise
                    await f.close()
                    file_path.unlink()
                    raise ValueError(f"File exceeds size limit: {self.max_size} bytes")
                
                await f.write(chunk)
                sha256.update(chunk)
        
        checksum = sha256.hexdigest()
        
        logger.info("Upload complete",
                   session_id=session_id,
                   filename=filename,
                   size=size,
                   checksum=checksum[:16] + "...")
        
        return file_path, checksum, size
    
    async def finalize_session(self, session_id: str) -> list[dict]:
        """
        Finalize an upload session.
        
        Returns:
            List of uploaded file info
        """
        session_dir = self.upload_dir / session_id
        if not session_dir.exists():
            raise ValueError(f"Invalid session: {session_id}")
        
        files = []
        for path in session_dir.iterdir():
            if path.is_file():
                # Compute checksum
                sha256 = hashlib.sha256()
                with open(path, 'rb') as f:
                    for chunk in iter(lambda: f.read(65536), b''):
                        sha256.update(chunk)
                
                files.append({
                    "filename": path.name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "sha256": sha256.hexdigest(),
                })
        
        logger.info("Session finalized", session_id=session_id, files=len(files))
        return files
    
    async def cancel_session(self, session_id: str):
        """Cancel and clean up an upload session."""
        session_dir = self.upload_dir / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
            logger.info("Session cancelled", session_id=session_id)
    
    def get_file_path(self, session_id: str, filename: str) -> Path:
        """Get the path to an uploaded file."""
        return self.upload_dir / session_id / filename

    async def promote_session_to_run(self, session_id: str, run_id: str):
        """
        Promote an upload session to a run directory.
        
        Renames the session directory to the run ID.
        """
        session_dir = self.upload_dir / session_id
        run_dir = self.upload_dir / run_id
        
        if not session_dir.exists():
            raise ValueError(f"Upload session not found: {session_id}")
            
        if run_dir.exists():
            # If run dir exists (e.g. from previous attempt), merge files
            for file_path in session_dir.iterdir():
                if file_path.is_file():
                    shutil.move(str(file_path), str(run_dir / file_path.name))
            shutil.rmtree(session_dir)
        else:
            session_dir.rename(run_dir)
            
        logger.info("Promoted upload session", session_id=session_id, run_id=run_id)
