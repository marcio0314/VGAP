"""
VGAP Sample Data Routes

Database-backed sample data access with actual file downloads.
"""

from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vgap.api.routes.auth import get_current_user
from vgap.api.schemas import (
    SampleResponse, SampleListResponse, QCMetricsResponse,
    VariantResponse, VariantListResponse, LineageResponse,
)
from vgap.config import get_settings
from vgap.models import User, Sample, Run
from vgap.services.database import get_session

router = APIRouter()
settings = get_settings()


async def get_sample_by_id(session: AsyncSession, sample_id: UUID) -> Optional[Sample]:
    """Get sample by ID."""
    result = await session.execute(
        select(Sample).where(Sample.id == sample_id)
    )
    return result.scalar_one_or_none()


async def get_sample_by_sample_id(
    session: AsyncSession, 
    run_id: UUID, 
    sample_id: str
) -> Optional[Sample]:
    """Get sample by sample_id within a run."""
    result = await session.execute(
        select(Sample).where(
            Sample.run_id == run_id,
            Sample.sample_id == sample_id
        )
    )
    return result.scalar_one_or_none()


def sample_to_response(sample: Sample) -> SampleResponse:
    """Convert Sample model to response."""
    return SampleResponse(
        id=sample.id,
        run_id=sample.run_id,
        sample_id=sample.sample_id,
        status=sample.status.value,
        collection_date=sample.collection_date,
        host=sample.host,
        location=sample.location,
        protocol=sample.protocol,
        platform=sample.platform,
        is_control=sample.is_control,
        control_type=sample.control_type,
        created_at=sample.created_at,
    )


@router.get("/{sample_id}", response_model=SampleResponse)
async def get_sample(
    sample_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific sample."""
    sample = await get_sample_by_id(session, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found"
        )
    
    return sample_to_response(sample)


@router.get("/{sample_id}/qc", response_model=QCMetricsResponse)
async def get_sample_qc(
    sample_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get QC metrics for a sample.
    
    Loads metrics from the results directory.
    """
    sample = await get_sample_by_id(session, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(sample.run_id) / sample.sample_id
    qc_path = results_dir / "qc" / "metrics.json"
    
    if not qc_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QC metrics not available for this sample"
        )
    
    import json
    with open(qc_path) as f:
        metrics = json.load(f)
    
    return QCMetricsResponse(**metrics)


@router.get("/{sample_id}/variants", response_model=VariantListResponse)
async def get_sample_variants(
    sample_id: UUID,
    min_af: float = Query(0.0, ge=0.0, le=1.0, description="Minimum allele frequency"),
    min_depth: int = Query(0, ge=0, description="Minimum depth"),
    gene: Optional[str] = Query(None, description="Filter by gene"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get variants for a sample.
    
    Supports filtering by allele frequency, depth, and gene.
    """
    sample = await get_sample_by_id(session, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(sample.run_id) / sample.sample_id
    variants_path = results_dir / "variants" / "variants.json"
    
    if not variants_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variants not available for this sample"
        )
    
    import json
    with open(variants_path) as f:
        all_variants = json.load(f)
    
    # Apply filters
    filtered = []
    for v in all_variants:
        if v.get("allele_freq", 0) < min_af:
            continue
        if v.get("depth", 0) < min_depth:
            continue
        if gene and v.get("gene") != gene:
            continue
        filtered.append(VariantResponse(**v))
    
    return VariantListResponse(
        sample_id=sample_id,
        total=len(filtered),
        variants=filtered,
    )


@router.get("/{sample_id}/consensus")
async def get_sample_consensus(
    sample_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Download consensus sequence for a sample.
    
    Returns FASTA file.
    """
    sample = await get_sample_by_id(session, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(sample.run_id) / sample.sample_id
    consensus_path = results_dir / "consensus" / "consensus.fasta"
    
    if not consensus_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consensus sequence not available for this sample"
        )
    
    return FileResponse(
        path=consensus_path,
        media_type="text/plain",
        filename=f"{sample.sample_id}_consensus.fasta",
    )


@router.get("/{sample_id}/lineage", response_model=LineageResponse)
async def get_sample_lineage(
    sample_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get lineage assignment for a sample.
    
    Returns Pangolin and Nextclade results.
    """
    sample = await get_sample_by_id(session, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(sample.run_id) / sample.sample_id
    lineage_path = results_dir / "lineage" / "lineage.json"
    
    if not lineage_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lineage assignment not available for this sample"
        )
    
    import json
    with open(lineage_path) as f:
        lineage = json.load(f)
    
    return LineageResponse(**lineage)


@router.get("/{sample_id}/coverage")
async def get_sample_coverage(
    sample_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Download coverage file for a sample.
    
    Returns BED format file with per-position depth.
    """
    sample = await get_sample_by_id(session, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(sample.run_id) / sample.sample_id
    coverage_path = results_dir / "mapping" / "coverage.bed"
    
    if not coverage_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coverage file not available for this sample"
        )
    
    return FileResponse(
        path=coverage_path,
        media_type="text/plain",
        filename=f"{sample.sample_id}_coverage.bed",
    )


@router.get("/{sample_id}/vcf")
async def get_sample_vcf(
    sample_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Download VCF file for a sample.
    
    Returns variants in VCF format.
    """
    sample = await get_sample_by_id(session, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample {sample_id} not found"
        )
    
    results_dir = Path(settings.storage.results_dir) / str(sample.run_id) / sample.sample_id
    vcf_path = results_dir / "variants" / "variants.vcf"
    
    if not vcf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VCF file not available for this sample"
        )
    
    return FileResponse(
        path=vcf_path,
        media_type="text/plain",
        filename=f"{sample.sample_id}.vcf",
    )
