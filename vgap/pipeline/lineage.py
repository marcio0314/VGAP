"""
VGAP Lineage Assignment - Pangolin and Nextclade integration.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class LineageResult:
    """Lineage assignment result."""
    sample_id: str
    pangolin_lineage: Optional[str] = None
    pangolin_version: Optional[str] = None
    pangolin_conflict: Optional[float] = None
    nextclade_clade: Optional[str] = None
    nextclade_version: Optional[str] = None
    nextclade_qc: Optional[str] = None
    confidence: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class PangolinRunner:
    """Run pangolin for SARS-CoV-2 lineage assignment."""
    
    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path
    
    def get_version(self) -> str:
        try:
            r = subprocess.run(["pangolin", "--version"], capture_output=True, text=True)
            return r.stdout.strip()
        except Exception:
            return "unknown"
    
    def run(self, fasta: Path, output_dir: Path) -> list[LineageResult]:
        """Run pangolin on FASTA file."""
        output_csv = output_dir / "pangolin.csv"
        
        cmd = ["pangolin", str(fasta), "-o", str(output_dir), "--outfile", "pangolin.csv"]
        if self.data_path:
            cmd.extend(["--datadir", str(self.data_path)])
        
        logger.info("Running pangolin", fasta=str(fasta))
        subprocess.run(cmd, check=True, capture_output=True, timeout=3600)
        
        return self._parse_results(output_csv)
    
    def _parse_results(self, csv_path: Path) -> list[LineageResult]:
        """Parse pangolin CSV output."""
        results = []
        with open(csv_path) as f:
            header = f.readline().strip().split(',')
            for line in f:
                parts = line.strip().split(',')
                if len(parts) < 2:
                    continue
                
                data = dict(zip(header, parts))
                r = LineageResult(
                    sample_id=data.get('taxon', ''),
                    pangolin_lineage=data.get('lineage'),
                    pangolin_version=self.get_version(),
                    pangolin_conflict=float(data['conflict']) if data.get('conflict') else None,
                )
                results.append(r)
        return results


class NextcladeRunner:
    """Run Nextclade for clade assignment and QC."""
    
    def __init__(self, dataset: str = "sars-cov-2", data_path: Optional[Path] = None):
        self.dataset = dataset
        self.data_path = data_path
    
    def get_version(self) -> str:
        try:
            r = subprocess.run(["nextclade", "--version"], capture_output=True, text=True)
            return r.stdout.strip()
        except Exception:
            return "unknown"
    
    def run(self, fasta: Path, output_dir: Path) -> list[LineageResult]:
        """Run Nextclade on FASTA file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = ["nextclade", "run"]
        
        if self.data_path:
            cmd.extend(["--input-dataset", str(self.data_path)])
        else:
            cmd.extend(["--dataset-name", self.dataset])
            
        cmd.extend(["--output-all", str(output_dir), str(fasta)])
        
        logger.info("Running Nextclade", fasta=str(fasta))
        subprocess.run(cmd, check=True, capture_output=True, timeout=3600)
        
        return self._parse_results(output_dir / "nextclade.json")
    
    def _parse_results(self, json_path: Path) -> list[LineageResult]:
        """Parse Nextclade JSON output."""
        if not json_path.exists():
            return []
        
        results = []
        with open(json_path) as f:
            data = json.load(f)
        
        for item in data.get('results', []):
            r = LineageResult(
                sample_id=item.get('seqName', ''),
                nextclade_clade=item.get('clade'),
                nextclade_version=self.get_version(),
                nextclade_qc=item.get('qc', {}).get('overallStatus'),
            )
            results.append(r)
        return results


class LineagePipeline:
    """Combined lineage assignment pipeline."""
    
    def __init__(self, pangolin_data: Optional[Path] = None,
                 nextclade_data: Optional[Path] = None):
        self.pangolin = PangolinRunner(data_path=pangolin_data)
        self.nextclade = NextcladeRunner(data_path=nextclade_data)
    
    def run(self, fasta: Path, output_dir: Path) -> list[LineageResult]:
        """Run both pangolin and Nextclade."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run pangolin
        pangolin_results = {}
        try:
            for r in self.pangolin.run(fasta, output_dir / "pangolin"):
                pangolin_results[r.sample_id] = r
        except Exception as e:
            logger.warning("Pangolin failed", error=str(e))
        
        # Run Nextclade
        nextclade_results = {}
        try:
            for r in self.nextclade.run(fasta, output_dir / "nextclade"):
                nextclade_results[r.sample_id] = r
        except Exception as e:
            logger.warning("Nextclade failed", error=str(e))
        
        # Merge results
        all_ids = set(pangolin_results.keys()) | set(nextclade_results.keys())
        merged = []
        for sid in all_ids:
            p = pangolin_results.get(sid, LineageResult(sample_id=sid))
            n = nextclade_results.get(sid, LineageResult(sample_id=sid))
            
            merged.append(LineageResult(
                sample_id=sid,
                pangolin_lineage=p.pangolin_lineage,
                pangolin_version=p.pangolin_version,
                pangolin_conflict=p.pangolin_conflict,
                nextclade_clade=n.nextclade_clade,
                nextclade_version=n.nextclade_version,
                nextclade_qc=n.nextclade_qc,
            ))
        
        return merged
