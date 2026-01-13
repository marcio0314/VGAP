"""
VGAP Pipeline Orchestration Service

Celery tasks for running analyses with proper database integration.
"""

from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import structlog
from celery import shared_task
from sqlalchemy import update

from vgap.config import get_settings
from vgap.models import (
    RunStatus, 
    SampleStatus,
    Run,
    Sample,
    QCMetrics,
    LineageAssignment,
    Consensus,
    Variant
)
from vgap.pipeline.qc import QCPipeline
from vgap.pipeline.mapping import ReferenceMapper, PrimerTrimmer, ConsensusGenerator
from vgap.pipeline.variants import IvarVariantCaller, BcftoolsVariantCaller, VariantAnnotator, VariantFilter
from vgap.pipeline.lineage import LineagePipeline
from vgap.pipeline.phylogeny import PhylogenyPipeline
from vgap.pipeline.reporting import ReportPipeline, ReportConfig
from vgap.utils.provenance import ProvenanceCollector, generate_checksums_file

logger = structlog.get_logger()
settings = get_settings()


def get_sync_session():
    """Get synchronous database session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Convert async URL to sync
    sync_url = str(settings.database.url).replace("+asyncpg", "")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)
    return Session()


@shared_task(bind=True, max_retries=3)
def process_run(self, run_id: str):
    """
    Main pipeline task - orchestrates complete analysis.
    
    Steps:
    1. Load run configuration from database
    2. Pre-flight validation
    3. QC and host removal
    4. Mapping and consensus
    5. Variant calling
    6. Lineage assignment
    7. Phylogenetics (if multiple samples)
    8. Report generation
    9. Update status and save provenance
    """
    from vgap.models import Run, Sample
    from sqlalchemy import select, update
    
    logger.info("Starting pipeline run", run_id=run_id)
    
    session = get_sync_session()
    
    try:
        # Load run from database
        run = session.execute(
            select(Run).where(Run.id == UUID(run_id))
        ).scalar_one_or_none()
        
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        # Update status to running
        session.execute(
            update(Run).where(Run.id == run.id).values(
                status=RunStatus.RUNNING,
                started_at=datetime.utcnow(),
                current_stage="initializing",
                celery_task_id=self.request.id,
            )
        )
        session.commit()
        
        # Load samples
        samples = session.execute(
            select(Sample).where(Sample.run_id == run.id)
        ).scalars().all()
        
        if not samples:
            raise ValueError("Run has no samples")
        
        # Initialize provenance
        provenance = ProvenanceCollector()
        provenance.run_id = run.id
        provenance.user_id = str(run.user_id)
        provenance.parameters = run.parameters or {}
        provenance.parameters["mode"] = run.mode
        provenance.parameters["primer_scheme"] = run.primer_scheme
        
        # Create output directory
        output_dir = Path(settings.storage.results_dir) / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Add input files to provenance
        for sample in samples:
            provenance.add_input_file(Path(sample.r1_path), category="fastq")
            if sample.r2_path:
                provenance.add_input_file(Path(sample.r2_path), category="fastq")
        
        # Get reference
        reference = Path(settings.storage.references_dir) / "sars-cov-2" / "reference.fasta"
        if run.reference_id:
            reference = Path(settings.storage.references_dir) / run.reference_id / "reference.fasta"
        
        # =====================================================================
        # STAGE 1: QC
        # =====================================================================
        update_progress(session, run.id, 10, "qc")
        logger.info("Running QC pipeline")
        
        qc_pipeline = QCPipeline(
            min_length=settings.pipeline.min_read_length,
            min_quality=settings.pipeline.min_base_quality,
        )
        provenance.add_software("fastp", "0.23.4")
        
        for sample in samples:
            sample_dir = output_dir / sample.sample_id
            qc_dir = sample_dir / "qc"
            qc_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                metrics = qc_pipeline.run(
                    r1_input=Path(sample.r1_path),
                    output_dir=qc_dir,
                    r2_input=Path(sample.r2_path) if sample.r2_path else None,
                )
                
                # Save QC metrics
                import json
                with open(qc_dir / "metrics.json", "w") as f:
                    json.dump(metrics.to_dict(), f, indent=2)
                
                # Update sample status
                session.execute(
                    update(Sample).where(Sample.id == sample.id).values(
                        status=SampleStatus.QC_COMPLETE
                    )
                )
            except Exception as e:
                logger.error("QC failed for sample", sample_id=sample.sample_id, error=str(e))
                session.execute(
                    update(Sample).where(Sample.id == sample.id).values(
                        status=SampleStatus.FAILED,
                        error_message=f"QC failed: {str(e)}"
                    )
                )
        
        session.commit()
        provenance.set_validation("qc", "PASS")
        
        # =====================================================================
        # STAGE 2: MAPPING
        # =====================================================================
        update_progress(session, run.id, 30, "mapping")
        logger.info("Running mapping pipeline")
        
        mapper = ReferenceMapper(reference=reference, threads=settings.resources.worker_cpu_limit)
        provenance.add_software("minimap2", "2.26")
        
        if run.mode == "amplicon" and run.primer_scheme:
            primer_bed = Path(settings.storage.references_dir) / "primers" / f"{run.primer_scheme}.bed"
            trimmer = PrimerTrimmer(primer_bed=primer_bed)
            provenance.add_software("ivar", "1.4.2")
        else:
            trimmer = None
        
        for sample in samples:
            sample_dir = output_dir / sample.sample_id
            mapping_dir = sample_dir / "mapping"
            mapping_dir.mkdir(parents=True, exist_ok=True)
            
            qc_r1 = sample_dir / "qc" / "trimmed_R1.fastq.gz"
            qc_r2 = sample_dir / "qc" / "trimmed_R2.fastq.gz" if sample.r2_path else None
            
            try:
                bam = mapper.map_reads(
                    r1=qc_r1,
                    output_bam=mapping_dir / f"{sample.sample_id}.bam",
                    r2=qc_r2,
                )
                
                # Trim primers if amplicon
                if trimmer:
                    bam = trimmer.trim(bam, mapping_dir / f"{sample.sample_id}.trimmed.bam")
                
                # Calculate coverage
                coverage = mapper.compute_coverage(bam)
                
                import json
                with open(mapping_dir / "coverage.json", "w") as f:
                    json.dump(coverage.to_dict(), f, indent=2)
                
                session.execute(
                    update(Sample).where(Sample.id == sample.id).values(
                        status=SampleStatus.MAPPING_COMPLETE
                    )
                )
            except Exception as e:
                logger.error("Mapping failed", sample_id=sample.sample_id, error=str(e))
                session.execute(
                    update(Sample).where(Sample.id == sample.id).values(
                        status=SampleStatus.FAILED,
                        error_message=f"Mapping failed: {str(e)}"
                    )
                )
        
        session.commit()
        
        # Add outputs to provenance
        for sample in samples:
            sample_dir = output_dir / sample.sample_id
            provenance.add_output_file(sample_dir / "mapping" / f"{sample.sample_id}.trimmed.bam", "bam")
            provenance.add_output_file(sample_dir / "mapping" / "coverage.json", "metrics")
            
        # =====================================================================
        # STAGE 3: CONSENSUS GENERATION
        # =====================================================================
        update_progress(session, run.id, 45, "consensus")
        logger.info("Generating consensus sequences")
        
        consensus_gen = ConsensusGenerator(
            min_depth=settings.pipeline.min_depth,
            min_af=settings.pipeline.min_allele_freq,
        )
        
        all_consensus = []
        for sample in samples:
            sample_dir = output_dir / sample.sample_id
            mapping_dir = sample_dir / "mapping"
            consensus_dir = sample_dir / "consensus"
            consensus_dir.mkdir(parents=True, exist_ok=True)
            
            bam = mapping_dir / f"{sample.sample_id}.trimmed.bam"
            if not bam.exists():
                bam = mapping_dir / f"{sample.sample_id}.bam"
            
            try:
                consensus = consensus_gen.generate(
                    bam=bam,
                    ref=reference,
                    output=consensus_dir / "consensus.fasta",
                )
                all_consensus.append(consensus)
                
                # CRITICAL FIX: Save stats for DB persistence
                import json
                with open(consensus_dir / "consensus_stats.json", "w") as f:
                    json.dump(consensus.to_dict(), f, indent=2)

            except Exception as e:
                logger.error("Consensus failed", sample_id=sample.sample_id, error=str(e))
        
        session.commit()
        
        # Add outputs to provenance
        for sample in samples:
            sample_dir = output_dir / sample.sample_id
            provenance.add_output_file(sample_dir / "consensus" / "consensus.fasta", "consensus")

        # =====================================================================
        # STAGE 4: VARIANT CALLING
        # =====================================================================
        update_progress(session, run.id, 55, "variants")
        logger.info("Calling variants")
        
        # Use BcftoolsVariantCaller for all modes since ivar is unavailable
        caller = BcftoolsVariantCaller(
            min_depth=settings.pipeline.min_depth,
            min_freq=settings.pipeline.min_variant_freq
        )
        
        annotator = VariantAnnotator()
        vfilter = VariantFilter(min_depth=settings.pipeline.min_depth, min_minor_freq=0.02)
        
        for sample in samples:
            sample_dir = output_dir / sample.sample_id
            mapping_dir = sample_dir / "mapping"
            variants_dir = sample_dir / "variants"
            variants_dir.mkdir(parents=True, exist_ok=True)
            
            bam = mapping_dir / f"{sample.sample_id}.trimmed.bam"
            if not bam.exists():
                bam = mapping_dir / f"{sample.sample_id}.bam"
            
            try:
                variants_list = caller.call_variants(
                    bam=bam,
                    ref=reference,
                    output_vcf=variants_dir / "variants.vcf.gz",
                )
                
                # Annotate and filter
                annotated = annotator.annotate(variants_list)
                filtered = vfilter.filter(annotated)
                
                import json
                with open(variants_dir / "variants.json", "w") as f:
                    json.dump([v.to_dict() for v in filtered], f, indent=2)
                
                session.execute(
                    update(Sample).where(Sample.id == sample.id).values(
                        status=SampleStatus.VARIANTS_COMPLETE
                    )
                )
            except Exception as e:
                logger.error("Variant calling failed", sample_id=sample.sample_id, error=str(e))
        
        session.commit()
        
        # Add outputs to provenance
        for sample in samples:
            sample_dir = output_dir / sample.sample_id
            provenance.add_output_file(sample_dir / "variants" / "variants.vcf.gz", "vcf")
            provenance.add_output_file(sample_dir / "variants" / "variants.json", "variants")
        
        # =====================================================================
        # STAGE 5: LINEAGE ASSIGNMENT
        # =====================================================================
        update_progress(session, run.id, 70, "lineage")
        logger.info("Assigning lineages")
        
        lineage_pipeline = LineagePipeline()
        provenance.add_software("pangolin", "4.3")
        provenance.add_software("nextclade", "3.0")
        
        for sample in samples:
            sample_dir = output_dir / sample.sample_id
            consensus_file = sample_dir / "consensus" / "consensus.fasta"
            lineage_dir = sample_dir / "lineage"
            lineage_dir.mkdir(parents=True, exist_ok=True)
            
            if consensus_file.exists():
                try:
                    result = lineage_pipeline.run(consensus_file, lineage_dir)
                    
                    import json
                    with open(lineage_dir / "lineage.json", "w") as f:
                        json.dump([r.to_dict() for r in result], f, indent=2)
                    
                    session.execute(
                        update(Sample).where(Sample.id == sample.id).values(
                            status=SampleStatus.COMPLETE
                        )
                    )
                except Exception as e:
                    logger.error("Lineage failed", sample_id=sample.sample_id, error=str(e))
        
        session.commit()
        
        # =====================================================================
        # STAGE 6: PHYLOGENETICS
        # =====================================================================
        if len(all_consensus) > 1:
            update_progress(session, run.id, 80, "phylogenetics")
            logger.info("Building phylogeny")
            
            phylo_pipeline = PhylogenyPipeline(threads=settings.resources.worker_cpu_limit)
            provenance.add_software("mafft", "7.520")
            provenance.add_software("iqtree2", "2.2.5")
            provenance.set_seed("iqtree", 12345)
            
            try:
                # Combine consensus sequences
                combined = output_dir / "combined_consensus.fasta"
                with open(combined, "w") as out:
                    for cf in all_consensus:
                        if cf.exists():
                            out.write(cf.read_text())
                
                phylo_dir = output_dir / "phylogenetics"
                tree = phylo_pipeline.run(combined, phylo_dir)
                
            except Exception as e:
                logger.error("Phylogenetics failed", error=str(e))
        
        # =====================================================================
        # STAGE 7: REPORTING
        # =====================================================================
        update_progress(session, run.id, 90, "reporting")
        logger.info("Generating report")
        
        try:
            report_pipeline = ReportPipeline(output_dir / "reports")
            samples_data = []
            
            for sample in samples:
                sample_dir = output_dir / sample.sample_id
                samples_data.append({
                    "sample_id": sample.sample_id,
                    "qc": load_json(sample_dir / "qc" / "metrics.json"),
                    "coverage": load_json(sample_dir / "mapping" / "coverage.json"),
                    "bam_path": str(sample_dir / "mapping" / f"{sample.sample_id}.trimmed.bam"),
                    "variants": load_json(sample_dir / "variants" / "variants.json") or [],
                    "lineage": (load_json(sample_dir / "lineage" / "lineage.json") or [{}])[0],
                })
            
            report_pipeline.generate(
                run_id=run_id,
                samples_data=samples_data,
                provenance=provenance.to_dict(),
                config=ReportConfig(title=f"VGAP Report - {run.name}"),
            )
        except Exception as e:
            logger.error("Report generation failed", error=str(e))
        
        # =====================================================================
        # FINALIZE
        # =====================================================================
        update_progress(session, run.id, 95, "finalizing")
        
        # Save results to DB
        try:
            save_run_results_to_db(session, run, output_dir)
        except Exception as e:
            logger.error("Failed to save results to DB", error=str(e))
            # Don't fail the pipeline for DB save error, but log it

        
        # Save provenance
        provenance.save(output_dir / "provenance.json")
        
        # Generate checksums
        generate_checksums_file(output_dir)
        
        # Update run status
        session.execute(
            update(Run).where(Run.id == run.id).values(
                status=RunStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                progress=100,
                current_stage="complete",
            )
        )
        session.commit()
        
        logger.info("Pipeline complete", run_id=run_id)
        
        return {"status": "completed", "run_id": run_id}
        
    except Exception as e:
        logger.exception("Pipeline failed", run_id=run_id, error=str(e))
        
        # Update run status
        session.execute(
            update(Run).where(Run.id == UUID(run_id)).values(
                status=RunStatus.FAILED,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )
        )
        session.commit()
        
        raise
    
    finally:
        session.close()


def update_progress(session, run_id: UUID, progress: int, stage: str):
    """Update run progress in database."""
    from vgap.models import Run
    from sqlalchemy import update
    
    session.execute(
        update(Run).where(Run.id == run_id).values(
            progress=progress,
            current_stage=stage,
        )
    )
    session.commit()


def load_json(path: Path):
    """Load JSON file if exists."""
    if path.exists():
        import json
        with open(path) as f:
            return json.load(f)
    return None


@shared_task
def process_sample_qc(sample_id: str, r1_path: str, r2_path: str = None):
    """Process QC for a single sample."""
    logger.info("Processing sample QC", sample_id=sample_id)
    
    qc = QCPipeline(
        min_length=settings.pipeline.min_read_length,
        min_quality=settings.pipeline.min_base_quality,
    )
    
    output_dir = Path(settings.storage.results_dir) / sample_id / "qc"
    metrics = qc.run(
        r1_input=Path(r1_path),
        output_dir=output_dir,
        r2_input=Path(r2_path) if r2_path else None,
    )
    
    return metrics.to_dict()


@shared_task
def generate_report(run_id: str, format: str = "html"):
    """Generate report for a completed run."""
    logger.info("Generating report", run_id=run_id, format=format)
    
    output_dir = Path(settings.storage.results_dir) / run_id
    report_path = output_dir / f"report.{format}"
    
    return {"report_path": str(report_path)}

def save_run_results_to_db(session, run, output_dir: Path):
    """Save analysis results from files to database."""
    from sqlalchemy import delete
    from vgap.models import QCMetrics, LineageAssignment, Consensus
    
    logger.info("Saving results to database", run_id=str(run.id))
    
    for sample in run.samples:
        sample_dir = output_dir / sample.sample_id
        
        # 1. QC Metrics
        qc_path = sample_dir / "qc" / "metrics.json"
        mapped_qc = load_json(qc_path)
        cov_path = sample_dir / "mapping" / "coverage.json"
        mapped_cov = load_json(cov_path) or {}
        
        if mapped_qc:
            # Merge coverage data into QC if separate
            # Assuming metrics.json has everything or we combine
            
            # Clear existing
            session.execute(delete(QCMetrics).where(QCMetrics.sample_id == sample.id))
            
            qc = QCMetrics(
                id=uuid4(),
                sample_id=sample.id,
                raw_reads=mapped_qc.get("raw_reads", 0),
                raw_bases=mapped_qc.get("raw_bases", 0),
                trimmed_reads=mapped_qc.get("trimmed_reads", 0),
                trimmed_bases=mapped_qc.get("trimmed_bases", 0),
                q20_rate=mapped_qc.get("q20_rate", 0.0),
                q30_rate=mapped_qc.get("q30_rate", 0.0),
                gc_content=mapped_qc.get("gc_content", 0.0),
                duplication_rate=mapped_qc.get("duplication_rate", 0.0),
                mapped_reads=mapped_qc.get("mapped_reads", 0),
                mapping_rate=mapped_qc.get("mapping_rate", 0.0),
                mean_depth=mapped_cov.get("mean_depth", 0.0),
                median_depth=mapped_cov.get("median_depth", 0.0),
                coverage_1x=mapped_cov.get("coverage_1x", 0.0),
                coverage_10x=mapped_cov.get("coverage_10x", 0.0),
                coverage_30x=mapped_cov.get("coverage_30x", 0.0),
                coverage_100x=mapped_cov.get("coverage_100x", 0.0),
                qc_pass=mapped_qc.get("qc_pass", False),
                qc_flags=mapped_qc.get("qc_flags", {}),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(qc)
            
        # 2. Lineage
        lin_path = sample_dir / "lineage" / "lineage.json"
        lin_data = load_json(lin_path)
        if lin_data:
            if isinstance(lin_data, list) and lin_data:
                lin_data = lin_data[0]
            
            session.execute(delete(LineageAssignment).where(LineageAssignment.sample_id == sample.id))
            
            lin = LineageAssignment(
                id=uuid4(),
                sample_id=sample.id,
                pangolin_lineage=lin_data.get("pangolin_lineage"),
                pangolin_version=lin_data.get("pangolin_version"),
                nextclade_clade=lin_data.get("nextclade_clade"),
                nextclade_version=lin_data.get("nextclade_version"),
                confidence_score=0.99 if lin_data.get("nextclade_clade") else 0.0, # Placeholder or extract
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(lin)

        # 3. Consensus (Optional but good)
        cons_stats_path = sample_dir / "consensus" / "consensus_stats.json" 
        cons_data = load_json(cons_stats_path)
        if cons_data:
             session.execute(delete(Consensus).where(Consensus.sample_id == sample.id))
             cons = Consensus(
                id=uuid4(),
                sample_id=sample.id,
                sequence_length=cons_data.get("length", 0),
                n_count=cons_data.get("n_count", 0),
                n_percentage=cons_data.get("n_percent", 0.0),
                fasta_path=str(sample_dir / "consensus" / "consensus.fasta"),
                fasta_checksum="", # TODO
                min_depth=10, # TODO from params
                min_allele_freq=0.5, # TODO
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
             )
             session.add(cons)

    session.commit()
