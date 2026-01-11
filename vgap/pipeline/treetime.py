"""
VGAP TreeTime Integration Module

Time-scaled phylogenetic analysis using TreeTime for molecular clock
estimation and ancestral state reconstruction.
"""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import structlog

logger = structlog.get_logger()


@dataclass
class TreeTimeResult:
    """Result from TreeTime analysis."""
    
    tree_path: Path
    dated_tree_path: Path
    root_date: Optional[datetime]
    clock_rate: float
    clock_rate_std: float
    r_squared: float
    num_tips: int
    ancestral_sequences_path: Optional[Path]
    molecular_clock_valid: bool
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tree_path": str(self.tree_path),
            "dated_tree_path": str(self.dated_tree_path),
            "root_date": self.root_date.isoformat() if self.root_date else None,
            "clock_rate": self.clock_rate,
            "clock_rate_std": self.clock_rate_std,
            "r_squared": self.r_squared,
            "num_tips": self.num_tips,
            "ancestral_sequences_path": str(self.ancestral_sequences_path) if self.ancestral_sequences_path else None,
            "molecular_clock_valid": self.molecular_clock_valid,
            "warnings": self.warnings,
        }


@dataclass
class DateInfo:
    """Date information for a sample."""
    sample_id: str
    date: datetime
    
    def to_treetime_format(self) -> str:
        """Format for TreeTime metadata file."""
        return f"{self.sample_id}\t{self.date.strftime('%Y-%m-%d')}"


class TreeTimePipeline:
    """
    Time-scaled phylogenetic analysis using TreeTime.
    
    Estimates molecular clock, dates internal nodes, and reconstructs
    ancestral sequences.
    """
    
    def __init__(
        self,
        clock_rate: Optional[float] = None,
        coalescent: str = "skyline",
        confidence: bool = True,
    ):
        """
        Initialize TreeTime pipeline.
        
        Args:
            clock_rate: Fixed clock rate (subs/site/year), None for auto
            coalescent: Coalescent model (skyline, const, opt)
            confidence: Calculate confidence intervals
        """
        self.clock_rate = clock_rate
        self.coalescent = coalescent
        self.confidence = confidence
    
    def create_metadata(
        self,
        dates: List[DateInfo],
        output_path: Path,
    ) -> Path:
        """Create metadata file for TreeTime."""
        with open(output_path, 'w') as f:
            f.write("name\tdate\n")
            for d in dates:
                f.write(f"{d.sample_id}\t{d.date.strftime('%Y-%m-%d')}\n")
        return output_path
    
    def run(
        self,
        alignment: Path,
        tree: Path,
        dates: List[DateInfo],
        output_dir: Path,
        reroot: bool = True,
        ancestral: bool = True,
    ) -> TreeTimeResult:
        """
        Run TreeTime analysis.
        
        Args:
            alignment: Path to aligned FASTA
            tree: Path to input tree (Newick)
            dates: List of DateInfo with sample dates
            output_dir: Output directory
            reroot: Re-root tree to optimize clock
            ancestral: Reconstruct ancestral sequences
        
        Returns:
            TreeTimeResult with dated tree and clock info
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create metadata file
        metadata_path = output_dir / "dates.tsv"
        self.create_metadata(dates, metadata_path)
        
        # Build command
        cmd = [
            "treetime",
            "--tree", str(tree),
            "--aln", str(alignment),
            "--dates", str(metadata_path),
            "--outdir", str(output_dir),
            "--coalescent", self.coalescent,
        ]
        
        if self.clock_rate:
            cmd.extend(["--clock-rate", str(self.clock_rate)])
        
        if reroot:
            cmd.append("--reroot")
            cmd.append("best")
        
        if self.confidence:
            cmd.append("--confidence")
        
        if ancestral:
            cmd.append("--ancestral")
        
        logger.info("Running TreeTime", cmd=" ".join(cmd))
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 min timeout
                cwd=output_dir,
            )
            
            if result.returncode != 0:
                logger.error("TreeTime failed", stderr=result.stderr[:1000])
                return TreeTimeResult(
                    tree_path=tree,
                    dated_tree_path=tree,
                    root_date=None,
                    clock_rate=0.0,
                    clock_rate_std=0.0,
                    r_squared=0.0,
                    num_tips=len(dates),
                    ancestral_sequences_path=None,
                    molecular_clock_valid=False,
                    warnings=["TreeTime failed: " + result.stderr[:500]],
                )
            
            # Parse results
            dated_tree = output_dir / "timetree.nexus"
            if not dated_tree.exists():
                dated_tree = output_dir / "timetree.nwk"
            
            ancestral_path = output_dir / "ancestral_sequences.fasta"
            if not ancestral_path.exists():
                ancestral_path = None
            
            # Parse molecular clock info
            clock_info = self._parse_clock_info(output_dir)
            
            return TreeTimeResult(
                tree_path=tree,
                dated_tree_path=dated_tree,
                root_date=clock_info.get("root_date"),
                clock_rate=clock_info.get("clock_rate", 0.0),
                clock_rate_std=clock_info.get("clock_rate_std", 0.0),
                r_squared=clock_info.get("r_squared", 0.0),
                num_tips=len(dates),
                ancestral_sequences_path=ancestral_path,
                molecular_clock_valid=clock_info.get("r_squared", 0) > 0.5,
                warnings=clock_info.get("warnings", []),
            )
            
        except subprocess.TimeoutExpired:
            return TreeTimeResult(
                tree_path=tree,
                dated_tree_path=tree,
                root_date=None,
                clock_rate=0.0,
                clock_rate_std=0.0,
                r_squared=0.0,
                num_tips=len(dates),
                ancestral_sequences_path=None,
                molecular_clock_valid=False,
                warnings=["TreeTime timed out after 30 minutes"],
            )
        except Exception as e:
            logger.exception("TreeTime failed")
            return TreeTimeResult(
                tree_path=tree,
                dated_tree_path=tree,
                root_date=None,
                clock_rate=0.0,
                clock_rate_std=0.0,
                r_squared=0.0,
                num_tips=len(dates),
                ancestral_sequences_path=None,
                molecular_clock_valid=False,
                warnings=[str(e)],
            )
    
    def _parse_clock_info(self, output_dir: Path) -> Dict[str, Any]:
        """Parse molecular clock information from TreeTime output."""
        info = {
            "clock_rate": 0.0,
            "clock_rate_std": 0.0,
            "r_squared": 0.0,
            "root_date": None,
            "warnings": [],
        }
        
        # Try to parse molecular_clock.txt
        clock_file = output_dir / "molecular_clock.txt"
        if clock_file.exists():
            try:
                with open(clock_file) as f:
                    content = f.read()
                
                for line in content.split("\n"):
                    if "rate:" in line.lower():
                        parts = line.split(":")
                        if len(parts) >= 2:
                            rate_str = parts[1].strip().split()[0]
                            info["clock_rate"] = float(rate_str)
                    elif "r^2:" in line.lower() or "r2:" in line.lower():
                        parts = line.split(":")
                        if len(parts) >= 2:
                            info["r_squared"] = float(parts[1].strip().split()[0])
                    elif "root:" in line.lower():
                        parts = line.split(":")
                        if len(parts) >= 2:
                            try:
                                date_str = parts[1].strip().split()[0]
                                info["root_date"] = datetime.strptime(date_str, "%Y-%m-%d")
                            except:
                                pass
            except Exception as e:
                info["warnings"].append(f"Could not parse clock file: {e}")
        
        # Try to parse dates.tsv for validation
        dates_file = output_dir / "dates.tsv"
        if dates_file.exists():
            try:
                with open(dates_file) as f:
                    lines = f.readlines()
                if len(lines) < 5:
                    info["warnings"].append("Too few samples for reliable dating")
            except:
                pass
        
        return info


class TreeAnnotator:
    """Annotate phylogenetic trees with metadata."""
    
    def __init__(self):
        pass
    
    def annotate(
        self,
        tree: Path,
        metadata: Dict[str, Dict[str, Any]],
        output_path: Path,
        format: str = "nexus",
    ) -> Path:
        """
        Annotate tree with metadata.
        
        Args:
            tree: Path to tree file
            metadata: Dict mapping sample_id to metadata dict
            output_path: Output file path
            format: Output format (nexus, newick)
        
        Returns:
            Path to annotated tree
        """
        # Read tree
        with open(tree) as f:
            tree_content = f.read()
        
        if format == "nexus":
            # Create NEXUS with annotations
            nexus_content = self._create_annotated_nexus(tree_content, metadata)
            with open(output_path, 'w') as f:
                f.write(nexus_content)
        else:
            # For Newick, just copy (annotations not supported)
            with open(output_path, 'w') as f:
                f.write(tree_content)
        
        return output_path
    
    def _create_annotated_nexus(
        self,
        tree_newick: str,
        metadata: Dict[str, Dict[str, Any]],
    ) -> str:
        """Create NEXUS format with annotations."""
        lines = [
            "#NEXUS",
            "",
            "BEGIN TAXA;",
            f"    DIMENSIONS NTAX={len(metadata)};",
            "    TAXLABELS",
        ]
        
        for sample_id in metadata:
            lines.append(f"        {sample_id}")
        
        lines.extend([
            "    ;",
            "END;",
            "",
            "BEGIN TREES;",
            f"    TREE tree1 = {tree_newick}",
            "END;",
            "",
            "BEGIN TRAITS;",
        ])
        
        # Add trait definitions
        if metadata:
            first_sample = list(metadata.values())[0]
            trait_names = list(first_sample.keys())
            lines.append(f"    Dimensions NTraits={len(trait_names)};")
            lines.append(f"    Format labels=yes missing=?;")
            lines.append(f"    TraitLabels {' '.join(trait_names)};")
            lines.append("    Matrix")
            
            for sample_id, traits in metadata.items():
                values = [str(traits.get(t, "?")) for t in trait_names]
                lines.append(f"        {sample_id} {' '.join(values)}")
            
            lines.append("    ;")
        
        lines.extend([
            "END;",
        ])
        
        return "\n".join(lines)
    
    def add_clade_colors(
        self,
        tree: Path,
        clade_colors: Dict[str, str],
        output_path: Path,
    ) -> Path:
        """Add clade-specific colors to tree for visualization."""
        # This creates a FigTree-compatible annotation
        with open(tree) as f:
            tree_content = f.read()
        
        # Add color annotations in NEXUS format
        lines = [
            "#NEXUS",
            "",
            "BEGIN TREES;",
            f"    TREE tree1 = {tree_content}",
            "END;",
            "",
            "BEGIN FIGTREE;",
        ]
        
        for clade, color in clade_colors.items():
            lines.append(f"    set appearance.branchColorAttribute=\"{clade}\";")
        
        lines.append("END;")
        
        with open(output_path, 'w') as f:
            f.write("\n".join(lines))
        
        return output_path
