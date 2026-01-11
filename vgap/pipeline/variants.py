"""
VGAP Variant Calling Pipeline - Detect and filter variants.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class Variant:
    """Single variant call."""
    chrom: str
    pos: int
    ref: str
    alt: str
    depth: int
    allele_freq: float
    gene: Optional[str] = None
    aa_change: Optional[str] = None
    is_consensus: bool = True
    is_minor: bool = False
    filter_status: str = "PASS"

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


class IvarVariantCaller:
    """Variant calling for amplicon data using ivar."""
    
    def __init__(self, min_depth: int = 10, min_freq: float = 0.02, min_quality: int = 20):
        self.min_depth = min_depth
        self.min_freq = min_freq
        self.min_quality = min_quality
    
    def call_variants(self, bam: Path, ref: Path, output_tsv: Path) -> list[Variant]:
        """Call variants with ivar."""
        prefix = str(output_tsv).replace('.tsv', '')
        
        mpileup = ["samtools", "mpileup", "-aa", "-A", "-d", "0",
                   "-Q", str(self.min_quality), "--reference", str(ref), str(bam)]
        ivar = ["ivar", "variants", "-p", prefix, "-r", str(ref),
                "-t", str(self.min_freq), "-m", str(self.min_depth)]
        
        p1 = subprocess.Popen(mpileup, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(ivar, stdin=p1.stdout, stderr=subprocess.PIPE)
        p1.stdout.close()
        p2.communicate(timeout=3600)
        
        return self._parse_tsv(output_tsv)
    
    def _parse_tsv(self, tsv_path: Path) -> list[Variant]:
        """Parse ivar variants TSV."""
        variants = []
        with open(tsv_path) as f:
            header = f.readline()
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 10:
                    continue
                
                af = float(parts[10]) if len(parts) > 10 else 0.0
                v = Variant(
                    chrom=parts[0],
                    pos=int(parts[1]),
                    ref=parts[2],
                    alt=parts[3],
                    depth=int(parts[11]) if len(parts) > 11 else 0,
                    allele_freq=af,
                    is_consensus=af >= 0.5,
                    is_minor=af < 0.5 and af >= self.min_freq,
                )
                variants.append(v)
        return variants


class BcftoolsVariantCaller:
    """Variant calling using bcftools."""
    
    def __init__(self, min_depth: int = 10, min_freq: float = 0.02):
        self.min_depth = min_depth
        self.min_freq = min_freq
    
    def call_variants(self, bam: Path, ref: Path, output_vcf: Path) -> list[Variant]:
        """Call variants with bcftools."""
        mpileup = ["bcftools", "mpileup", "-Ou", "-f", str(ref),
                   "-d", "10000", "-Q", "20", str(bam)]
        call = ["bcftools", "call", "-Oz", "-m", "-v", "-o", str(output_vcf)]
        
        p1 = subprocess.Popen(mpileup, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(call, stdin=p1.stdout, stderr=subprocess.PIPE)
        p1.stdout.close()
        p2.communicate(timeout=3600)
        
        subprocess.run(["bcftools", "index", str(output_vcf)], check=True)
        return self._parse_vcf(output_vcf)
    
    def _parse_vcf(self, vcf_path: Path) -> list[Variant]:
        """Parse VCF file."""
        variants = []
        result = subprocess.run(["bcftools", "view", str(vcf_path)],
                              capture_output=True, text=True)
        
        for line in result.stdout.split('\n'):
            if line.startswith('#') or not line:
                continue
            parts = line.split('\t')
            if len(parts) < 10:
                continue
            
            # Extract depth and AF from INFO
            info = dict(x.split('=') if '=' in x else (x, True) 
                       for x in parts[7].split(';'))
            depth = int(info.get('DP', 0))
            
            v = Variant(
                chrom=parts[0],
                pos=int(parts[1]),
                ref=parts[3],
                alt=parts[4],
                depth=depth,
                allele_freq=1.0,  # Simplified
                filter_status=parts[6],
            )
            variants.append(v)
        return variants


class VariantAnnotator:
    """Annotate variants with gene/protein changes."""
    
    def __init__(self, gff_path: Optional[Path] = None):
        self.gff_path = gff_path
        self.genes = {}
        if gff_path and gff_path.exists():
            self._load_gff()
    
    def _load_gff(self):
        """Load gene annotations from GFF."""
        with open(self.gff_path) as f:
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) < 9 or parts[2] != 'CDS':
                    continue
                
                attrs = dict(x.split('=') for x in parts[8].split(';') if '=' in x)
                name = attrs.get('gene', attrs.get('Name', ''))
                if name:
                    self.genes[name] = (int(parts[3]), int(parts[4]))
    
    def annotate(self, variants: list[Variant]) -> list[Variant]:
        """Add gene annotations to variants."""
        for v in variants:
            for gene, (start, end) in self.genes.items():
                if start <= v.pos <= end:
                    v.gene = gene
                    # Simplified codon calculation
                    codon_pos = (v.pos - start) // 3 + 1
                    v.aa_change = f"{gene}:{codon_pos}"
                    break
        return variants


class VariantFilter:
    """Filter variants based on quality metrics."""
    
    def __init__(self, min_depth: int = 10, min_consensus_freq: float = 0.5,
                 min_minor_freq: float = 0.02):
        self.min_depth = min_depth
        self.min_consensus_freq = min_consensus_freq
        self.min_minor_freq = min_minor_freq
    
    def filter(self, variants: list[Variant]) -> list[Variant]:
        """Apply filters and classify variants."""
        filtered = []
        for v in variants:
            if v.depth < self.min_depth:
                v.filter_status = "LOW_DEPTH"
            elif v.allele_freq < self.min_minor_freq:
                v.filter_status = "LOW_FREQ"
                continue  # Skip very low frequency
            else:
                v.filter_status = "PASS"
            
            v.is_consensus = v.allele_freq >= self.min_consensus_freq
            v.is_minor = v.allele_freq < self.min_consensus_freq
            filtered.append(v)
        
        return filtered
