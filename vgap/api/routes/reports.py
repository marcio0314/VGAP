"""
VGAP Report Generation Routes

Fresh report generation - no caching. Every request generates a new report.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vgap.api.routes.auth import get_current_user
from vgap.api.schemas import (
    ReportGenerateRequest, ReportResponse, ReportFormat,
)
from vgap.config import get_settings
from vgap.models import User, Run, RunStatus
from vgap.services.database import get_session
from vgap.services.run_service import get_run_by_id, get_run_samples
from vgap.pipeline.reporting import ReportPipeline, ReportConfig, ReportData
from vgap.utils.provenance import ProvenanceCollector

router = APIRouter()
settings = get_settings()


async def load_run_data(session: AsyncSession, run: Run) -> dict:
    """Load all data needed for report generation."""
    samples = await get_run_samples(session, run.id)
    results_dir = Path(settings.storage.results_dir) / str(run.id)
    
    samples_data = []
    for sample in samples:
        sample_dir = results_dir / sample.sample_id
        
        # Load QC metrics
        qc = {}
        qc_path = sample_dir / "qc" / "metrics.json"
        if qc_path.exists():
            import json
            with open(qc_path) as f:
                qc = json.load(f)
        
        # Load coverage
        coverage = {}
        cov_path = sample_dir / "mapping" / "coverage.json"
        if cov_path.exists():
            import json
            with open(cov_path) as f:
                coverage = json.load(f)
        
        # Load variants
        variants = []
        var_path = sample_dir / "variants" / "variants.json"
        if var_path.exists():
            import json
            with open(var_path) as f:
                variants = json.load(f)
        
        # Load lineage
        lineage = None
        lin_path = sample_dir / "lineage" / "lineage.json"
        if lin_path.exists():
            import json
            with open(lin_path) as f:
                lineage = json.load(f)
        
        samples_data.append({
            "sample_id": sample.sample_id,
            "qc": qc,
            "coverage": coverage,
            "variants": variants,
            "lineage": lineage,
        })
    
    return {
        "run": run,
        "samples": samples_data,
    }


@router.post("/{run_id}/generate", response_model=ReportResponse)
async def generate_report(
    run_id: UUID,
    request: ReportGenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a fresh report for a completed run.
    
    IMPORTANT: Reports are ALWAYS generated fresh. No caching.
    Each request produces a new report with unique ID and timestamp.
    """
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    if run.status != RunStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reports only available for completed runs. Current status: {run.status.value}"
        )
    
    # Generate unique report ID
    report_id = uuid4()
    generation_timestamp = datetime.utcnow()
    
    # Load run data
    data = await load_run_data(session, run)
    
    # Load provenance
    results_dir = Path(settings.storage.results_dir) / str(run_id)
    provenance_path = results_dir / "provenance.json"
    provenance = None
    if provenance_path.exists():
        provenance = ProvenanceCollector.load(provenance_path).to_dict()
    
    # Create report output directory
    reports_dir = results_dir / "reports" / str(report_id)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure report
    config = ReportConfig(
        title=request.title or f"VGAP Analysis Report - {run.name}",
        include_figures=request.include_figures,
        include_tables=request.include_tables,
        include_provenance=request.include_provenance,
        include_methods=request.include_methods,
        figure_format=request.figure_format or "svg",
        figure_dpi=request.figure_dpi or 300,
    )
    
    # Generate report - ALWAYS FRESH
    pipeline = ReportPipeline(reports_dir)
    outputs = pipeline.generate(
        run_id=str(run_id),
        samples_data=data["samples"],
        provenance=provenance,
        config=config,
    )
    
    # Write generation metadata
    import json
    metadata = {
        "report_id": str(report_id),
        "run_id": str(run_id),
        "generated_at": generation_timestamp.isoformat(),
        "generated_by": str(current_user.id),
        "format": request.format.value,
        "config": {
            "title": config.title,
            "include_figures": config.include_figures,
            "include_tables": config.include_tables,
            "figure_format": config.figure_format,
        }
    }
    
    
    with open(reports_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    # [RECOVERY FIX] Create 'latest' copy for "View Report" button
    # The frontend expects reports/run_id/exports/report -> reports/report.html
    try:
        import shutil
        latest_report_path = results_dir / "reports" / "report.html"
        generated_report = outputs  # outputs is the path returned by pipeline.generate
        if generated_report and generated_report.exists():
            shutil.copy2(generated_report, latest_report_path)
    except Exception as e:
        # Don't fail the request if copy fails, just log
        print(f"Failed to update latest report link: {e}")

    
    return ReportResponse(
        report_id=report_id,
        run_id=run_id,
        format=request.format.value,
        generated_at=generation_timestamp,
        download_url=f"/api/v1/reports/{run_id}/download/{report_id}",
        expires_at=None,  # Reports don't expire
    )


@router.get("/{run_id}/download/{report_id}")
async def download_report(
    run_id: UUID,
    report_id: UUID,
    format: Optional[str] = Query("html", description="Report format (html, pdf)"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Download a generated report.
    
    Returns the actual report file, not a cached version.
    """
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    reports_dir = Path(settings.storage.results_dir) / str(run_id) / "reports" / str(report_id)
    
    if not reports_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found"
        )
    
    if format == "html":
        report_path = reports_dir / "report.html"
        media_type = "text/html"
    elif format == "pdf":
        # For PDF, return HTML with print-optimized headers
        report_path = reports_dir / "report.html"
        media_type = "text/html"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}"
        )
    
    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found"
        )
    
    return FileResponse(
        path=report_path,
        media_type=media_type,
        filename=f"vgap_report_{run.run_code}_{report_id}.{format}",
    )


@router.get("/{run_id}/figures/{figure_name}")
async def get_figure(
    run_id: UUID,
    figure_name: str,
    format: Optional[str] = Query("svg", description="Figure format (svg, png)"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific figure from a report.
    
    Returns the figure file in the requested format.
    """
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(run_id)
    figure_path = results_dir / "figures" / f"{figure_name}.{format}"
    
    if not figure_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Figure {figure_name} not found"
        )
    
    media_type = "image/svg+xml" if format == "svg" else "image/png"
    
    return FileResponse(
        path=figure_path,
        media_type=media_type,
        filename=f"{figure_name}.{format}",
    )


@router.get("/{run_id}/exports/{export_type}")
async def download_export(
    run_id: UUID,
    export_type: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Download raw data exports.
    
    Available exports:
    - variants: variants.tsv
    - consensus: consensus.fasta
    - coverage: coverage.bed
    - provenance: provenance.json
    - checksums: checksums.txt
    """
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(run_id)
    
    export_map = {
        "variants": ("variants.tsv", "text/tab-separated-values"),
        "consensus": ("consensus.fasta", "text/plain"),
        "coverage": ("coverage.bed", "text/plain"),
        "provenance": ("provenance.json", "application/json"),
        "checksums": ("checksums.txt", "text/plain"),
        "samples_summary": ("reports/samples_summary.tsv", "text/tab-separated-values"),
        "report": ("reports/report.html", "text/html"),
    }
    
    if export_type not in export_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown export type: {export_type}. Available: {list(export_map.keys())}"
        )
    
    filename, media_type = export_map[export_type]
    file_path = results_dir / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export file not found: {export_type}"
        )
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=f"{run.run_code}_{filename}",
    )


@router.get("/{run_id}/package")
async def download_results_package(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Download complete results package as ZIP.
    
    Includes all outputs: consensus, variants, reports, provenance.
    """
    import zipfile
    import io
    
    run = await get_run_by_id(session, run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    if run.status != RunStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Package only available for completed runs"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(run_id)
    
    if not results_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results directory not found"
        )
    
    # Create ZIP in memory
    buffer = io.BytesIO()
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in results_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(results_dir)
                zf.write(file_path, arcname)
    
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=vgap_{run.run_code}_results.zip"
        }
    )
