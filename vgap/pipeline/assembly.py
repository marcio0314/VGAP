"""
VGAP De Novo Assembly Module

SPAdes and megahit integration for shotgun/metagenomic data.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class AssemblyResult:
    """De novo assembly result."""
    contigs_path: Path
    num_contigs: int = 0
    total_length: int = 0
    n50: int = 0
    largest_contig: int = 0
    gc_content: float = 0.0


class SPAdesAssembler:
    """SPAdes assembler for viral genomes."""
    
    def __init__(self, threads: int = 4, memory_gb: int = 16):
        self.threads = threads
        self.memory_gb = memory_gb
    
    def get_version(self) -> str:
        try:
            result = subprocess.run(["spades.py", "--version"],
                                  capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except Exception:
            return "unknown"
    
    def assemble(
        self,
        r1_path: Path,
        output_dir: Path,
        r2_path: Optional[Path] = None,
        mode: str = "rnaviral",
    ) -> AssemblyResult:
        """
        Run SPAdes assembly.
        
        Args:
            r1_path: Path to R1 FASTQ
            output_dir: Output directory
            r2_path: Optional R2 FASTQ
            mode: Assembly mode (rnaviral, metaviral, or default)
        
        Returns:
            AssemblyResult with contigs and stats
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = ["spades.py"]
        
        # Mode selection
        if mode == "rnaviral":
            cmd.append("--rnaviral")
        elif mode == "metaviral":
            cmd.append("--metaviral")
        
        # Input files
        if r2_path:
            cmd.extend(["-1", str(r1_path), "-2", str(r2_path)])
        else:
            cmd.extend(["-s", str(r1_path)])
        
        cmd.extend([
            "-o", str(output_dir),
            "-t", str(self.threads),
            "-m", str(self.memory_gb),
            "--careful",
        ])
        
        logger.info("Running SPAdes", mode=mode, output=str(output_dir))
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=14400)
        except subprocess.CalledProcessError as e:
            logger.error("SPAdes failed", stderr=e.stderr.decode())
            raise
        
        # Parse results
        contigs_path = output_dir / "contigs.fasta"
        if not contigs_path.exists():
            contigs_path = output_dir / "scaffolds.fasta"
        
        result = self._compute_stats(contigs_path)
        
        logger.info("SPAdes complete",
                   contigs=result.num_contigs,
                   n50=result.n50,
                   total_length=result.total_length)
        
        return result
    
    def _compute_stats(self, contigs_path: Path) -> AssemblyResult:
        """Compute assembly statistics."""
        result = AssemblyResult(contigs_path=contigs_path)
        
        if not contigs_path.exists():
            return result
        
        lengths = []
        gc_sum = 0
        total_bases = 0
        
        with open(contigs_path) as f:
            current_len = 0
            current_gc = 0
            for line in f:
                if line.startswith('>'):
                    if current_len > 0:
                        lengths.append(current_len)
                        gc_sum += current_gc
                        total_bases += current_len
                    current_len = 0
                    current_gc = 0
                else:
                    seq = line.strip().upper()
                    current_len += len(seq)
                    current_gc += seq.count('G') + seq.count('C')
            
            if current_len > 0:
                lengths.append(current_len)
                gc_sum += current_gc
                total_bases += current_len
        
        if not lengths:
            return result
        
        result.num_contigs = len(lengths)
        result.total_length = sum(lengths)
        result.largest_contig = max(lengths)
        result.gc_content = gc_sum / total_bases if total_bases else 0
        
        # N50 calculation
        lengths.sort(reverse=True)
        cumsum = 0
        half = result.total_length / 2
        for length in lengths:
            cumsum += length
            if cumsum >= half:
                result.n50 = length
                break
        
        return result


class MegahitAssembler:
    """Megahit assembler for metagenomic data."""
    
    def __init__(self, threads: int = 4, memory_gb: int = 16):
        self.threads = threads
        self.memory_bytes = memory_gb * 1024 * 1024 * 1024
    
    def get_version(self) -> str:
        try:
            result = subprocess.run(["megahit", "--version"],
                                  capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except Exception:
            return "unknown"
    
    def assemble(
        self,
        r1_path: Path,
        output_dir: Path,
        r2_path: Optional[Path] = None,
        min_contig_len: int = 500,
    ) -> AssemblyResult:
        """
        Run Megahit assembly.
        
        Args:
            r1_path: Path to R1 FASTQ
            output_dir: Output directory
            r2_path: Optional R2 FASTQ
            min_contig_len: Minimum contig length
        
        Returns:
            AssemblyResult with contigs and stats
        """
        # Megahit wants a fresh output directory
        if output_dir.exists():
            import shutil
            shutil.rmtree(output_dir)
        
        cmd = ["megahit"]
        
        if r2_path:
            cmd.extend(["-1", str(r1_path), "-2", str(r2_path)])
        else:
            cmd.extend(["-r", str(r1_path)])
        
        cmd.extend([
            "-o", str(output_dir),
            "-t", str(self.threads),
            "-m", str(self.memory_bytes),
            "--min-contig-len", str(min_contig_len),
        ])
        
        logger.info("Running Megahit", output=str(output_dir))
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=14400)
        except subprocess.CalledProcessError as e:
            logger.error("Megahit failed", stderr=e.stderr.decode())
            raise
        
        contigs_path = output_dir / "final.contigs.fa"
        result = SPAdesAssembler._compute_stats(None, contigs_path)
        
        logger.info("Megahit complete",
                   contigs=result.num_contigs,
                   n50=result.n50)
        
        return result


class AssemblyPipeline:
    """Assembly pipeline with multiple assemblers."""
    
    def __init__(
        self,
        assembler: str = "spades",
        threads: int = 4,
        memory_gb: int = 16,
    ):
        self.assembler = assembler
        if assembler == "spades":
            self._assembler = SPAdesAssembler(threads, memory_gb)
        else:
            self._assembler = MegahitAssembler(threads, memory_gb)
    
    def run(
        self,
        r1_path: Path,
        output_dir: Path,
        r2_path: Optional[Path] = None,
        reference: Optional[Path] = None,
    ) -> AssemblyResult:
        """
        Run assembly pipeline.
        
        If reference is provided, also scaffolds against it.
        """
        result = self._assembler.assemble(r1_path, output_dir, r2_path)
        
        # Optional reference scaffolding
        if reference and result.contigs_path.exists():
            self._scaffold_to_reference(result.contigs_path, reference, output_dir)
        
        return result
    
    def _scaffold_to_reference(
        self,
        contigs: Path,
        reference: Path,
        output_dir: Path,
    ):
        """Scaffold contigs to reference using minimap2."""
        paf_path = output_dir / "contigs_vs_ref.paf"
        
        cmd = ["minimap2", "-x", "asm5", str(reference), str(contigs)]
        
        with open(paf_path, 'w') as out:
            subprocess.run(cmd, stdout=out, check=True)
        
        logger.info("Contigs aligned to reference", paf=str(paf_path))
