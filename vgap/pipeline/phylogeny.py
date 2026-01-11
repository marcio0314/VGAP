"""
VGAP Phylogenetics - MSA and tree construction.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class TreeResult:
    """Phylogenetic tree result."""
    newick_path: Path
    json_path: Optional[Path] = None
    num_sequences: int = 0
    alignment_length: int = 0
    
    def to_dict(self) -> dict:
        return {
            "newick_path": str(self.newick_path),
            "json_path": str(self.json_path) if self.json_path else None,
            "num_sequences": self.num_sequences,
            "alignment_length": self.alignment_length,
        }


class MAFFTAligner:
    """Multiple sequence alignment with MAFFT."""
    
    def __init__(self, threads: int = 4):
        self.threads = threads
    
    def align(self, input_fasta: Path, output_fasta: Path) -> Path:
        """Run MAFFT alignment."""
        cmd = ["mafft", "--auto", "--thread", str(self.threads), str(input_fasta)]
        
        logger.info("Running MAFFT alignment", input=str(input_fasta))
        with open(output_fasta, 'w') as out:
            subprocess.run(cmd, stdout=out, check=True, timeout=7200)
        
        return output_fasta


class SiteMasker:
    """Mask problematic sites in alignment."""
    
    def __init__(self, mask_positions: Optional[list[int]] = None):
        # Default problematic sites for SARS-CoV-2
        self.mask_positions = mask_positions or list(range(1, 56)) + list(range(29804, 29904))
    
    def mask(self, input_fasta: Path, output_fasta: Path) -> Path:
        """Mask specified positions with N."""
        sequences = {}
        current_id = None
        current_seq = []
        
        with open(input_fasta) as f:
            for line in f:
                if line.startswith('>'):
                    if current_id:
                        sequences[current_id] = ''.join(current_seq)
                    current_id = line.strip()
                    current_seq = []
                else:
                    current_seq.append(line.strip())
            if current_id:
                sequences[current_id] = ''.join(current_seq)
        
        with open(output_fasta, 'w') as out:
            for seq_id, seq in sequences.items():
                masked = list(seq)
                for pos in self.mask_positions:
                    if 0 < pos <= len(masked):
                        masked[pos - 1] = 'N'
                
                out.write(seq_id + '\n')
                masked_seq = ''.join(masked)
                for i in range(0, len(masked_seq), 80):
                    out.write(masked_seq[i:i+80] + '\n')
        
        return output_fasta


class IQTreeBuilder:
    """Build phylogenetic tree with IQ-TREE."""
    
    def __init__(self, threads: int = 4, bootstrap: int = 1000):
        self.threads = threads
        self.bootstrap = bootstrap
    
    def build(self, alignment: Path, output_prefix: Path, seed: int = 12345) -> TreeResult:
        """Build tree with IQ-TREE."""
        cmd = [
            "iqtree2", "-s", str(alignment),
            "-m", "GTR+G4",
            "-T", str(self.threads),
            "-B", str(self.bootstrap),
            "--prefix", str(output_prefix),
            "-seed", str(seed),
        ]
        
        logger.info("Building tree with IQ-TREE", alignment=str(alignment))
        subprocess.run(cmd, check=True, timeout=14400, capture_output=True)
        
        # Count sequences
        num_seqs = sum(1 for line in open(alignment) if line.startswith('>'))
        
        # Get alignment length
        with open(alignment) as f:
            f.readline()  # Skip header
            first_seq = ''
            for line in f:
                if line.startswith('>'):
                    break
                first_seq += line.strip()
        
        return TreeResult(
            newick_path=Path(str(output_prefix) + ".treefile"),
            num_sequences=num_seqs,
            alignment_length=len(first_seq),
        )


class PhylogenyPipeline:
    """Complete phylogenetics pipeline."""
    
    def __init__(self, threads: int = 4, bootstrap: int = 1000,
                 mask_sites: bool = True):
        self.aligner = MAFFTAligner(threads=threads)
        self.masker = SiteMasker() if mask_sites else None
        self.tree_builder = IQTreeBuilder(threads=threads, bootstrap=bootstrap)
    
    def run(self, input_fasta: Path, output_dir: Path, seed: int = 12345) -> TreeResult:
        """Run complete phylogenetics pipeline."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Align
        aligned = output_dir / "aligned.fasta"
        self.aligner.align(input_fasta, aligned)
        
        # Mask
        if self.masker:
            masked = output_dir / "masked.fasta"
            self.masker.mask(aligned, masked)
            tree_input = masked
        else:
            tree_input = aligned
        
        # Build tree
        result = self.tree_builder.build(tree_input, output_dir / "tree", seed=seed)
        
        logger.info("Phylogenetics complete", 
                   sequences=result.num_sequences,
                   tree=str(result.newick_path))
        
        return result
