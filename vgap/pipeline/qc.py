"""
VGAP Quality Control Pipeline

Handles adapter trimming, quality filtering, and host removal.
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import structlog

from vgap.config import get_settings
from vgap.utils.provenance import ProvenanceCollector

logger = structlog.get_logger()
settings = get_settings()


@dataclass
class QCMetrics:
    """Container for QC metrics."""
    
    # Raw reads
    raw_reads: int = 0
    raw_bases: int = 0
    
    # After trimming
    trimmed_reads: int = 0
    trimmed_bases: int = 0
    
    # Quality metrics
    q20_rate: float = 0.0
    q30_rate: float = 0.0
    gc_content: float = 0.0
    duplication_rate: float = 0.0
    
    # Read length
    read_length_mean: float = 0.0
    read_length_min: int = 0
    read_length_max: int = 0
    
    # Host removal
    host_reads: int = 0
    host_removal_rate: float = 0.0
    
    # Pass/fail
    qc_pass: bool = True
    qc_flags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_reads": self.raw_reads,
            "raw_bases": self.raw_bases,
            "trimmed_reads": self.trimmed_reads,
            "trimmed_bases": self.trimmed_bases,
            "q20_rate": self.q20_rate,
            "q30_rate": self.q30_rate,
            "gc_content": self.gc_content,
            "duplication_rate": self.duplication_rate,
            "read_length_mean": self.read_length_mean,
            "read_length_min": self.read_length_min,
            "read_length_max": self.read_length_max,
            "host_reads": self.host_reads,
            "host_removal_rate": self.host_removal_rate,
            "qc_pass": self.qc_pass,
            "qc_flags": self.qc_flags,
        }


class FastpRunner:
    """
    Wrapper for fastp quality control tool.
    
    Handles adapter trimming, quality filtering, and generates detailed reports.
    """
    
    def __init__(
        self,
        min_length: int = 50,
        min_quality: int = 20,
        cut_front: bool = True,
        cut_tail: bool = True,
        threads: int = 4,
    ):
        self.min_length = min_length
        self.min_quality = min_quality
        self.cut_front = cut_front
        self.cut_tail = cut_tail
        self.threads = threads
    
    def get_version(self) -> str:
        """Get fastp version."""
        try:
            result = subprocess.run(
                ["fastp", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stderr.strip().replace("fastp ", "")
        except Exception:
            return "unknown"
    
    def run(
        self,
        r1_input: Path,
        r1_output: Path,
        r2_input: Optional[Path] = None,
        r2_output: Optional[Path] = None,
        json_output: Optional[Path] = None,
        html_output: Optional[Path] = None,
        provenance: Optional[ProvenanceCollector] = None,
    ) -> QCMetrics:
        """
        Run fastp on input FASTQ files.
        
        Args:
            r1_input: Path to R1 input FASTQ
            r1_output: Path for R1 output FASTQ
            r2_input: Optional path to R2 input FASTQ
            r2_output: Optional path for R2 output FASTQ
            json_output: Path for JSON report output
            html_output: Path for HTML report output
            provenance: Optional provenance collector
        
        Returns:
            QCMetrics object with all quality metrics
        """
        if json_output is None:
            json_output = r1_output.parent / "fastp.json"
        if html_output is None:
            html_output = r1_output.parent / "fastp.html"
        
        # Build command
        cmd = [
            "fastp",
            "-i", str(r1_input),
            "-o", str(r1_output),
            "-j", str(json_output),
            "-h", str(html_output),
            "-l", str(self.min_length),
            "-q", str(self.min_quality),
            "-w", str(self.threads),
            "--detect_adapter_for_pe",
        ]
        
        if self.cut_front:
            cmd.append("--cut_front")
        if self.cut_tail:
            cmd.append("--cut_tail")
        
        if r2_input and r2_output:
            cmd.extend(["-I", str(r2_input), "-O", str(r2_output)])
        
        logger.info("Running fastp", command=" ".join(cmd))
        
        # Record in provenance
        if provenance:
            provenance.add_software("fastp", self.get_version())
            provenance.add_command("fastp", cmd)
        
        # Execute
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode != 0:
                logger.error("fastp failed", stderr=result.stderr)
                raise RuntimeError(f"fastp failed: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("fastp timed out after 1 hour")
        
        # Parse JSON report
        metrics = self._parse_report(json_output)
        
        return metrics
    
    def _parse_report(self, json_path: Path) -> QCMetrics:
        """Parse fastp JSON report into QCMetrics."""
        with open(json_path, 'r') as f:
            report = json.load(f)
        
        metrics = QCMetrics()
        
        # Summary statistics
        summary = report.get("summary", {})
        before = summary.get("before_filtering", {})
        after = summary.get("after_filtering", {})
        
        metrics.raw_reads = before.get("total_reads", 0)
        metrics.raw_bases = before.get("total_bases", 0)
        metrics.trimmed_reads = after.get("total_reads", 0)
        metrics.trimmed_bases = after.get("total_bases", 0)
        
        metrics.q20_rate = after.get("q20_rate", 0.0)
        metrics.q30_rate = after.get("q30_rate", 0.0)
        metrics.gc_content = after.get("gc_content", 0.0)
        
        # Duplication
        dup = report.get("duplication", {})
        metrics.duplication_rate = dup.get("rate", 0.0)
        
        # Read length
        read_len = report.get("read1_after_filtering", {})
        if read_len:
            metrics.read_length_mean = read_len.get("total_bases", 0) / max(read_len.get("total_reads", 1), 1)
        
        # Filter stats
        filter_result = report.get("filtering_result", {})
        passed = filter_result.get("passed_filter_reads", 0)
        low_quality = filter_result.get("low_quality_reads", 0)
        
        # QC flags
        if metrics.q30_rate < 0.5:
            metrics.qc_flags.append("LOW_Q30")
        if metrics.trimmed_reads < 1000:
            metrics.qc_flags.append("LOW_READ_COUNT")
        if metrics.duplication_rate > 0.5:
            metrics.qc_flags.append("HIGH_DUPLICATION")
        
        metrics.qc_pass = len(metrics.qc_flags) == 0
        
        return metrics


class HostRemover:
    """
    Remove host reads by mapping to host genome and extracting unmapped reads.
    """
    
    def __init__(
        self,
        host_reference: Path,
        threads: int = 4,
    ):
        self.host_reference = host_reference
        self.threads = threads
    
    def get_minimap2_version(self) -> str:
        """Get minimap2 version."""
        try:
            result = subprocess.run(
                ["minimap2", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"
    
    def remove_host(
        self,
        r1_input: Path,
        r1_output: Path,
        r2_input: Optional[Path] = None,
        r2_output: Optional[Path] = None,
        work_dir: Optional[Path] = None,
        provenance: Optional[ProvenanceCollector] = None,
    ) -> tuple[int, float]:
        """
        Remove host reads from input FASTQ.
        
        Maps reads to host genome and extracts unmapped reads.
        
        Args:
            r1_input: Path to R1 input FASTQ
            r1_output: Path for R1 output FASTQ (host-removed)
            r2_input: Optional path to R2 input FASTQ
            r2_output: Optional path for R2 output FASTQ
            work_dir: Working directory for intermediate files
            provenance: Optional provenance collector
        
        Returns:
            Tuple of (host_reads_count, host_removal_rate)
        """
        if work_dir is None:
            work_dir = r1_output.parent
        
        if not self.host_reference.exists():
            logger.warning("Host reference not found, skipping host removal")
            # Just copy input to output
            import shutil
            shutil.copy(r1_input, r1_output)
            if r2_input and r2_output:
                shutil.copy(r2_input, r2_output)
            return 0, 0.0
        
        # Step 1: Map to host with minimap2
        bam_file = work_dir / "host_mapped.bam"
        
        if r2_input:
            map_cmd = [
                "minimap2",
                "-ax", "sr",
                "-t", str(self.threads),
                "--secondary=no",
                str(self.host_reference),
                str(r1_input),
                str(r2_input),
            ]
        else:
            map_cmd = [
                "minimap2",
                "-ax", "sr",
                "-t", str(self.threads),
                "--secondary=no",
                str(self.host_reference),
                str(r1_input),
            ]
        
        # Pipe to samtools for BAM conversion
        sort_cmd = ["samtools", "sort", "-@", str(self.threads), "-o", str(bam_file)]
        
        logger.info("Mapping to host genome", reference=str(self.host_reference))
        
        if provenance:
            provenance.add_software("minimap2", self.get_minimap2_version())
            provenance.add_command("minimap2", map_cmd)
        
        # Execute mapping
        p1 = subprocess.Popen(map_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2 = subprocess.Popen(sort_cmd, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.stdout.close()
        _, stderr = p2.communicate(timeout=7200)  # 2 hour timeout
        
        if p2.returncode != 0:
            raise RuntimeError(f"Host mapping failed: {stderr.decode()}")
        
        # Index BAM
        subprocess.run(["samtools", "index", str(bam_file)], check=True)
        
        # Step 2: Extract unmapped reads
        # Count total and mapped reads
        flagstat = subprocess.run(
            ["samtools", "flagstat", str(bam_file)],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse flagstat output
        total_reads = 0
        mapped_reads = 0
        for line in flagstat.stdout.split('\n'):
            if 'total' in line and 'in total' in line:
                total_reads = int(line.split()[0])
            elif 'mapped (' in line:
                mapped_reads = int(line.split()[0])
        
        host_removal_rate = mapped_reads / max(total_reads, 1)
        
        # Extract unmapped reads to FASTQ
        if r2_input:
            # Paired-end: extract both unmapped
            extract_cmd = [
                "samtools", "fastq",
                "-f", "4",  # Unmapped flag
                "-1", str(r1_output),
                "-2", str(r2_output),
                "-0", "/dev/null",
                "-s", "/dev/null",
                str(bam_file)
            ]
        else:
            # Single-end
            extract_cmd = [
                "samtools", "fastq",
                "-f", "4",
                str(bam_file)
            ]
        
        if r2_input:
            subprocess.run(extract_cmd, check=True)
        else:
            with open(r1_output, 'w') as out:
                subprocess.run(extract_cmd, stdout=out, check=True)
        
        # Cleanup
        bam_file.unlink()
        Path(str(bam_file) + ".bai").unlink()
        
        logger.info(
            "Host removal complete",
            total_reads=total_reads,
            host_reads=mapped_reads,
            removal_rate=host_removal_rate
        )
        
        return mapped_reads, host_removal_rate


class ContaminationChecker:
    """
    Check for contamination in negative controls.
    """
    
    def __init__(
        self,
        target_reference: Path,
        threshold: float = 0.001,  # 0.1%
    ):
        self.target_reference = target_reference
        self.threshold = threshold
    
    def check_negative_control(
        self,
        r1_path: Path,
        r2_path: Optional[Path] = None,
    ) -> tuple[bool, float]:
        """
        Check if a negative control sample has contamination.
        
        Returns:
            Tuple of (is_contaminated, contamination_rate)
        """
        if not self.target_reference.exists():
            logger.warning("Target reference not found, skipping contamination check")
            return False, 0.0
        
        # Quick mapping to target
        cmd = ["minimap2", "-ax", "sr", "-t", "4", str(self.target_reference)]
        
        if r2_path:
            cmd.extend([str(r1_path), str(r2_path)])
        else:
            cmd.append(str(r1_path))
        
        # Count mapped reads
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2 = subprocess.Popen(
            ["samtools", "view", "-c", "-F", "4", "-"],
            stdin=p1.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        p1.stdout.close()
        stdout, _ = p2.communicate(timeout=1800)
        
        mapped_reads = int(stdout.decode().strip() or 0)
        
        # Count total reads (quick estimate from file)
        total_cmd = ["zcat" if str(r1_path).endswith('.gz') else "cat", str(r1_path)]
        count_cmd = ["wc", "-l"]
        
        p1 = subprocess.Popen(total_cmd, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(count_cmd, stdin=p1.stdout, stdout=subprocess.PIPE)
        p1.stdout.close()
        stdout, _ = p2.communicate(timeout=300)
        
        total_lines = int(stdout.decode().strip())
        total_reads = total_lines // 4  # 4 lines per FASTQ record
        
        contamination_rate = mapped_reads / max(total_reads, 1)
        is_contaminated = contamination_rate > self.threshold
        
        if is_contaminated:
            logger.warning(
                "Negative control contaminated",
                mapped_reads=mapped_reads,
                total_reads=total_reads,
                rate=contamination_rate,
                threshold=self.threshold
            )
        
        return is_contaminated, contamination_rate


class QCPipeline:
    """
    Complete QC pipeline orchestrator.
    """
    
    def __init__(
        self,
        min_length: int = 50,
        min_quality: int = 20,
        host_reference: Optional[Path] = None,
        target_reference: Optional[Path] = None,
        enable_host_removal: bool = True,
        threads: int = 4,
    ):
        self.fastp = FastpRunner(
            min_length=min_length,
            min_quality=min_quality,
            threads=threads
        )
        
        self.host_remover = None
        if enable_host_removal and host_reference:
            self.host_remover = HostRemover(
                host_reference=host_reference,
                threads=threads
            )
        
        self.contamination_checker = None
        if target_reference:
            self.contamination_checker = ContaminationChecker(
                target_reference=target_reference
            )
    
    def run(
        self,
        r1_input: Path,
        output_dir: Path,
        r2_input: Optional[Path] = None,
        is_control: bool = False,
        provenance: Optional[ProvenanceCollector] = None,
    ) -> QCMetrics:
        """
        Run the complete QC pipeline on a sample.
        
        Steps:
        1. Adapter trimming and quality filtering (fastp)
        2. Host removal (optional)
        3. Contamination check (for controls)
        
        Args:
            r1_input: Path to R1 input FASTQ
            output_dir: Directory for output files
            r2_input: Optional path to R2 input FASTQ
            is_control: Whether this is a negative control
            provenance: Optional provenance collector
        
        Returns:
            QCMetrics with all quality information
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 1: fastp
        r1_trimmed = output_dir / "trimmed_R1.fastq.gz"
        r2_trimmed = output_dir / "trimmed_R2.fastq.gz" if r2_input else None
        
        logger.info("Running fastp QC", sample=r1_input.stem)
        
        metrics = self.fastp.run(
            r1_input=r1_input,
            r1_output=r1_trimmed,
            r2_input=r2_input,
            r2_output=r2_trimmed,
            json_output=output_dir / "fastp.json",
            html_output=output_dir / "fastp.html",
            provenance=provenance,
        )
        
        # Step 2: Host removal
        if self.host_remover:
            r1_dehost = output_dir / "dehost_R1.fastq.gz"
            r2_dehost = output_dir / "dehost_R2.fastq.gz" if r2_input else None
            
            logger.info("Removing host reads")
            
            host_reads, host_rate = self.host_remover.remove_host(
                r1_input=r1_trimmed,
                r1_output=r1_dehost,
                r2_input=r2_trimmed,
                r2_output=r2_dehost,
                work_dir=output_dir,
                provenance=provenance,
            )
            
            metrics.host_reads = host_reads
            metrics.host_removal_rate = host_rate
            
            # Use dehosted files for downstream
            r1_final = r1_dehost
            r2_final = r2_dehost
        else:
            r1_final = r1_trimmed
            r2_final = r2_trimmed
        
        # Step 3: Contamination check for controls
        if is_control and self.contamination_checker:
            logger.info("Checking negative control for contamination")
            
            is_contaminated, contam_rate = self.contamination_checker.check_negative_control(
                r1_path=r1_final,
                r2_path=r2_final,
            )
            
            if is_contaminated:
                metrics.qc_flags.append("CONTROL_CONTAMINATED")
                metrics.qc_pass = False
        
        logger.info(
            "QC pipeline complete",
            raw_reads=metrics.raw_reads,
            trimmed_reads=metrics.trimmed_reads,
            qc_pass=metrics.qc_pass,
            flags=metrics.qc_flags
        )
        
        return metrics
