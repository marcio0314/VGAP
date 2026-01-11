"""
VGAP Mapping Pipeline - Reference mapping and consensus generation.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class CoverageMetrics:
    """Coverage statistics."""
    genome_length: int = 0
    mean_depth: float = 0.0
    median_depth: float = 0.0
    coverage_1x: float = 0.0
    coverage_10x: float = 0.0
    coverage_30x: float = 0.0
    coverage_100x: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


@dataclass
class ConsensusResult:
    """Consensus sequence result."""
    fasta_path: Path
    sequence_length: int = 0
    n_count: int = 0
    n_percentage: float = 0.0
    checksum: str = ""
    min_depth: int = 10
    min_af: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d["fasta_path"] = str(self.fasta_path)
        return d


class ReferenceMapper:
    """Map reads to reference using minimap2."""
    
    def __init__(self, reference: Path, threads: int = 4):
        self.reference = reference
        self.threads = threads
    
    def map_reads(self, r1: Path, output_bam: Path, r2: Optional[Path] = None) -> Path:
        """Map reads and produce sorted BAM."""
        cmd = ["minimap2", "-ax", "sr", "-t", str(self.threads), str(self.reference)]
        cmd.extend([str(r1), str(r2)] if r2 else [str(r1)])
        
        sort_cmd = ["samtools", "sort", "-@", str(self.threads), "-o", str(output_bam)]
        
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2 = subprocess.Popen(sort_cmd, stdin=p1.stdout, stderr=subprocess.PIPE)
        p1.stdout.close()
        p2.communicate(timeout=7200)
        
        subprocess.run(["samtools", "index", str(output_bam)], check=True)
        return output_bam
    
    def compute_coverage(self, bam: Path) -> CoverageMetrics:
        """Compute coverage metrics from BAM."""
        result = subprocess.run(["samtools", "depth", "-a", str(bam)],
                              capture_output=True, text=True, check=True)
        
        depths = [int(l.split('\t')[2]) for l in result.stdout.strip().split('\n') if l]
        if not depths:
            return CoverageMetrics()
        
        import statistics
        m = CoverageMetrics(
            genome_length=len(depths),
            mean_depth=statistics.mean(depths),
            median_depth=statistics.median(depths),
            coverage_1x=sum(1 for d in depths if d >= 1) / len(depths),
            coverage_10x=sum(1 for d in depths if d >= 10) / len(depths),
            coverage_30x=sum(1 for d in depths if d >= 30) / len(depths),
            coverage_100x=sum(1 for d in depths if d >= 100) / len(depths),
        )
        return m


class ConsensusGenerator:
    """Generate consensus sequence."""
    
    def __init__(self, min_depth: int = 10, min_af: float = 0.5):
        self.min_depth = min_depth
        self.min_af = min_af
    
    def generate(self, bam: Path, ref: Path, output: Path) -> ConsensusResult:
        """Generate consensus using ivar."""
        prefix = str(output).replace('.fa', '')
        
        mpileup = ["samtools", "mpileup", "-aa", "-A", "-d", "0", "-Q", "20",
                   "--reference", str(ref), str(bam)]
        ivar = ["ivar", "consensus", "-p", prefix, "-t", str(self.min_af),
                "-m", str(self.min_depth), "-n", "N"]
        
        p1 = subprocess.Popen(mpileup, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(ivar, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.stdout.close()
        p2.communicate(timeout=3600)
        
        Path(prefix + ".fa").rename(output)
        
        with open(output) as f:
            seq = ''.join(l.strip() for l in f.readlines()[1:])
        
        import hashlib
        with open(output, 'rb') as f:
            checksum = hashlib.sha256(f.read()).hexdigest()
        
        return ConsensusResult(
            fasta_path=output,
            sequence_length=len(seq),
            n_count=seq.upper().count('N'),
            n_percentage=seq.upper().count('N') / max(len(seq), 1) * 100,
            checksum=checksum,
            min_depth=self.min_depth,
            min_af=self.min_af,
        )
