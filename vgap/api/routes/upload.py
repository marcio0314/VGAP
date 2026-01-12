from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from vgap.services.upload import UploadService

router = APIRouter(tags=["Upload"])

@router.post("/session")
async def create_upload_session():
    """
    Create a new upload session.
    
    Returns structured response with session_id and status.
    """
    upload_service = UploadService()
    session_id = await upload_service.create_upload_session()
    
    return {
        "session_id": session_id,
        "status": "IDLE",
        "message": "Upload session created. Ready to receive files.",
        "expected_next_step": "UPLOAD",
    }


@router.post("/{session_id}")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
):
    """
    Upload a file to a session.
    
    Files are streamed to disk without loading into memory.
    Returns structured response with upload status and validation info.
    """
    upload_service = UploadService()
    
    # Validate filename
    is_valid, error = upload_service.validate_filename(file.filename)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "sample_id": None,
                "status": "FAILED",
                "message": error,
                "expected_next_step": "FIX_FILENAME",
                "error_code": "INVALID_FILENAME",
                "remediation_hint": "Rename the file to use only alphanumeric characters, underscores, hyphens, and periods. No spaces allowed.",
            }
        )
    
    # Stream upload
    async def file_stream():
        while chunk := await file.read(65536):
            yield chunk
    
    try:
        path, checksum, size = await upload_service.stream_upload(
            session_id=session_id,
            filename=file.filename,
            stream=file_stream(),
        )
        
        # Extract sample ID from filename (remove extension)
        sample_id = file.filename
        for ext in ['.fastq.gz', '.fq.gz', '.fastq', '.fq']:
            if sample_id.lower().endswith(ext):
                sample_id = sample_id[:-len(ext)]
                break
        
        return {
            "sample_id": sample_id,
            "filename": file.filename,
            "size": size,
            "checksum": checksum,
            "status": "STORED",
            "message": f"File uploaded successfully ({size:,} bytes)",
            "expected_next_step": "CREATE_RUN",
        }
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "sample_id": None,
                "status": "FAILED",
                "message": str(e),
                "expected_next_step": "RETRY",
                "error_code": "UPLOAD_FAILED",
                "remediation_hint": "Check that the session ID is valid and the file is not too large.",
            }
        )


@router.get("/{session_id}/status")
async def get_upload_status(session_id: str):
    """
    Get the status of an upload session.
    
    Returns all files in the session and their status.
    """
    upload_service = UploadService()
    session_dir = upload_service.upload_dir / session_id
    
    if not session_dir.exists():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "session_id": session_id,
                "status": "NOT_FOUND",
                "message": f"Upload session {session_id} not found",
                "expected_next_step": "CREATE_SESSION",
                "error_code": "SESSION_NOT_FOUND",
            }
        )
    
    files = []
    for path in session_dir.iterdir():
        if path.is_file():
            files.append({
                "filename": path.name,
                "size": path.stat().st_size,
                "status": "STORED",
            })
    
    return {
        "session_id": session_id,
        "status": "READY" if files else "IDLE",
        "file_count": len(files),
        "files": files,
        "message": f"{len(files)} file(s) ready" if files else "No files uploaded yet",
        "expected_next_step": "CREATE_RUN" if files else "UPLOAD",
    }
