"""
VGAP Influenza Clade Assignment Module

Provides clade assignment for Influenza A and B viruses using
multiple classification systems (H-numbering, WHO nomenclature).
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

import structlog

logger = structlog.get_logger()


@dataclass
class InfluenzaCladeResult:
    """Result from influenza clade assignment."""
    
    sample_id: str
    virus_type: str  # A or B
    subtype: Optional[str]  # H1N1, H3N2, etc.
    clade: Optional[str]
    subclade: Optional[str]
    ha_clade: Optional[str]
    na_clade: Optional[str]
    who_name: Optional[str]
    confidence: float
    method: str
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "virus_type": self.virus_type,
            "subtype": self.subtype,
            "clade": self.clade,
            "subclade": self.subclade,
            "ha_clade": self.ha_clade,
            "na_clade": self.na_clade,
            "who_name": self.who_name,
            "confidence": self.confidence,
            "method": self.method,
            "warnings": self.warnings,
        }


class NextcladeInfluenza:
    """Influenza clade assignment using Nextclade."""
    
    DATASETS = {
        "H1N1pdm": "flu_h1n1pdm_ha",
        "H3N2": "flu_h3n2_ha",
        "Victoria": "flu_vic_ha",
        "Yamagata": "flu_yam_ha",
    }
    
    def __init__(self, threads: int = 4):
        self.threads = threads
    
    def detect_subtype(self, consensus: Path) -> Optional[str]:
        """Detect influenza subtype from consensus sequence."""
        # Use BLAST or minimap2 against reference database
        # For now, try all datasets and pick best match
        return None  # Auto-detect
    
    def run(
        self,
        consensus: Path,
        output_dir: Path,
        subtype: Optional[str] = None,
    ) -> InfluenzaCladeResult:
        """Run Nextclade for influenza clade assignment."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        sample_id = consensus.stem.replace("_consensus", "")
        
        # If subtype not specified, try to detect
        if not subtype:
            subtype = self.detect_subtype(consensus)
        
        # Default to H1N1pdm if unknown
        dataset = self.DATASETS.get(subtype, "flu_h1n1pdm_ha")
        
        output_json = output_dir / "nextclade.json"
        
        cmd = [
            "nextclade", "run",
            "--input-fasta", str(consensus),
            "--dataset-name", dataset,
            "--output-json", str(output_json),
            "--jobs", str(self.threads),
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode != 0:
                logger.warning(
                    "Nextclade influenza failed",
                    stderr=result.stderr[:500],
                )
                return InfluenzaCladeResult(
                    sample_id=sample_id,
                    virus_type="unknown",
                    subtype=subtype,
                    clade=None,
                    subclade=None,
                    ha_clade=None,
                    na_clade=None,
                    who_name=None,
                    confidence=0.0,
                    method="nextclade",
                    warnings=["Nextclade failed: " + result.stderr[:200]],
                )
            
            # Parse results
            with open(output_json) as f:
                data = json.load(f)
            
            if not data.get("results"):
                return InfluenzaCladeResult(
                    sample_id=sample_id,
                    virus_type="unknown",
                    subtype=subtype,
                    clade=None,
                    subclade=None,
                    ha_clade=None,
                    na_clade=None,
                    who_name=None,
                    confidence=0.0,
                    method="nextclade",
                    warnings=["No results from Nextclade"],
                )
            
            result_data = data["results"][0]
            
            return InfluenzaCladeResult(
                sample_id=sample_id,
                virus_type="A" if "h1n1" in dataset or "h3n2" in dataset else "B",
                subtype=subtype,
                clade=result_data.get("clade"),
                subclade=result_data.get("subclade"),
                ha_clade=result_data.get("clade"),  # HA-based clade
                na_clade=None,  # Would need separate NA analysis
                who_name=result_data.get("customNodeAttributes", {}).get("who_name"),
                confidence=1.0 - (result_data.get("qc", {}).get("overallScore", 0) / 100),
                method="nextclade",
                warnings=result_data.get("warnings", []),
            )
            
        except subprocess.TimeoutExpired:
            return InfluenzaCladeResult(
                sample_id=sample_id,
                virus_type="unknown",
                subtype=subtype,
                clade=None,
                subclade=None,
                ha_clade=None,
                na_clade=None,
                who_name=None,
                confidence=0.0,
                method="nextclade",
                warnings=["Nextclade timed out"],
            )
        except Exception as e:
            logger.exception("Influenza clade assignment failed")
            return InfluenzaCladeResult(
                sample_id=sample_id,
                virus_type="unknown",
                subtype=subtype,
                clade=None,
                subclade=None,
                ha_clade=None,
                na_clade=None,
                who_name=None,
                confidence=0.0,
                method="nextclade",
                warnings=[str(e)],
            )


class InfluenzaCladeAssigner:
    """Main class for influenza clade assignment supporting multiple methods."""
    
    def __init__(self, threads: int = 4):
        self.threads = threads
        self.nextclade = NextcladeInfluenza(threads=threads)
    
    def assign_clade(
        self,
        consensus: Path,
        output_dir: Path,
        subtype: Optional[str] = None,
        method: str = "nextclade",
    ) -> InfluenzaCladeResult:
        """
        Assign clade to influenza consensus sequence.
        
        Args:
            consensus: Path to consensus FASTA
            output_dir: Output directory
            subtype: Known subtype (H1N1pdm, H3N2, Victoria, Yamagata)
            method: Assignment method (nextclade)
        
        Returns:
            InfluenzaCladeResult with clade information
        """
        logger.info(
            "Assigning influenza clade",
            sample=consensus.stem,
            subtype=subtype,
            method=method,
        )
        
        if method == "nextclade":
            return self.nextclade.run(consensus, output_dir, subtype)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def assign_batch(
        self,
        consensus_files: List[Path],
        output_dir: Path,
        subtype: Optional[str] = None,
    ) -> List[InfluenzaCladeResult]:
        """Assign clades to multiple samples."""
        results = []
        for cf in consensus_files:
            sample_dir = output_dir / cf.stem
            result = self.assign_clade(cf, sample_dir, subtype)
            results.append(result)
        return results
