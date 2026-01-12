"""
VGAP Reference Database Manager

Handles downloading, versioning, and verification of reference databases.
All databases are sourced from authoritative public repositories.
"""

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.request import urlretrieve
from urllib.error import URLError

import structlog

from vgap.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class DatabaseStatus(str, Enum):
    """Database installation status."""
    NOT_INSTALLED = "not_installed"
    DOWNLOADING = "downloading"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    ERROR = "error"


@dataclass
class DatabaseInfo:
    """Information about an installed database."""
    name: str
    version: str
    status: DatabaseStatus
    path: Optional[Path] = None
    source_url: Optional[str] = None
    checksum: Optional[str] = None
    installed_at: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "path": str(self.path) if self.path else None,
            "source_url": self.source_url,
            "checksum": self.checksum,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "error_message": self.error_message,
        }


# Authoritative database sources
REFERENCE_SOURCES = {
    "sars-cov-2": {
        "name": "SARS-CoV-2 Reference Genome",
        "accession": "NC_045512.2",
        "fasta_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_045512.2&rettype=fasta&retmode=text",
        "gff_url": "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/009/858/895/GCF_009858895.2_ASM985889v3/GCF_009858895.2_ASM985889v3_genomic.gff.gz",
        "expected_length": 29903,
    },
}

PRIMER_SCHEMES = {
    "ARTIC-V3": {
        "name": "ARTIC v3",
        "url": "https://raw.githubusercontent.com/artic-network/artic-ncov2019/master/primer_schemes/nCoV-2019/V3/nCoV-2019.primer.bed",
        "amplicon_length": 400,
    },
    "ARTIC-V4": {
        "name": "ARTIC v4",
        "url": "https://raw.githubusercontent.com/artic-network/artic-ncov2019/master/primer_schemes/nCoV-2019/V4/SARS-CoV-2.scheme.bed",
        "amplicon_length": 400,
    },
    "ARTIC-V4.1": {
        "name": "ARTIC v4.1",
        "url": "https://raw.githubusercontent.com/artic-network/artic-ncov2019/master/primer_schemes/nCoV-2019/V4.1/SARS-CoV-2.scheme.bed",
        "amplicon_length": 400,
    },
    "ARTIC-V5.3.2": {
        "name": "ARTIC v5.3.2",
        "url": "https://raw.githubusercontent.com/artic-network/artic-ncov2019/master/primer_schemes/nCoV-2019/V5.3.2/SARS-CoV-2.scheme.bed",
        "amplicon_length": 400,
    },
}


class ReferenceManager:
    """
    Manages reference databases for VGAP.
    
    Responsible for:
    - Downloading reference genomes from NCBI
    - Downloading primer schemes from ARTIC Network
    - Verifying checksums and integrity
    - Tracking versions and installation status
    """
    
    def __init__(self, references_dir: Optional[Path] = None):
        self.references_dir = references_dir or Path(settings.storage.references_dir)
        self.references_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.references_dir / "manifest.json"
        self._load_manifest()
    
    def _load_manifest(self):
        """Load or create database manifest."""
        if self.manifest_path.exists():
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {
                "version": "1.0",
                "databases": {},
                "primers": {},
                "last_updated": None,
            }
    
    def _save_manifest(self):
        """Save database manifest."""
        self.manifest["last_updated"] = datetime.utcnow().isoformat()
        with open(self.manifest_path, "w") as f:
            json.dump(self.manifest, f, indent=2)
    
    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _download_file(self, url: str, dest: Path, description: str = "file") -> bool:
        """Download file from URL with logging."""
        logger.info(f"Downloading {description}", url=url, dest=str(dest))
        
        try:
            urlretrieve(url, dest)
            logger.info(f"Downloaded {description}", size=dest.stat().st_size)
            return True
        except URLError as e:
            logger.error(f"Failed to download {description}", error=str(e))
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading {description}", error=str(e))
            return False
    
    def get_inventory(self) -> dict:
        """Get complete database inventory."""
        inventory = {
            "references": {},
            "primers": {},
            "status": "operational",
            "missing_critical": [],
        }
        
        # Check references
        for ref_id, ref_info in REFERENCE_SOURCES.items():
            ref_dir = self.references_dir / ref_id
            fasta_path = ref_dir / "reference.fasta"
            
            if fasta_path.exists():
                db_info = self.manifest.get("databases", {}).get(ref_id, {})
                inventory["references"][ref_id] = {
                    "name": ref_info["name"],
                    "status": "installed",
                    "version": db_info.get("version", "unknown"),
                    "path": str(fasta_path),
                    "installed_at": db_info.get("installed_at"),
                }
            else:
                inventory["references"][ref_id] = {
                    "name": ref_info["name"],
                    "status": "not_installed",
                    "version": None,
                    "path": None,
                }
                inventory["missing_critical"].append(ref_id)
        
        # Check primer schemes
        primers_dir = self.references_dir / "primers"
        for scheme_id, scheme_info in PRIMER_SCHEMES.items():
            bed_path = primers_dir / f"{scheme_id}.bed"
            
            if bed_path.exists():
                inventory["primers"][scheme_id] = {
                    "name": scheme_info["name"],
                    "status": "installed",
                    "path": str(bed_path),
                    "amplicon_length": scheme_info["amplicon_length"],
                }
            else:
                inventory["primers"][scheme_id] = {
                    "name": scheme_info["name"],
                    "status": "not_installed",
                    "path": None,
                }
        
        if inventory["missing_critical"]:
            inventory["status"] = "incomplete"
        
        return inventory
    
    def bootstrap_sars_cov_2(self) -> DatabaseInfo:
        """
        Bootstrap SARS-CoV-2 reference database.
        
        Downloads from NCBI RefSeq:
        - Reference genome (NC_045512.2)
        - Gene annotations
        """
        ref_id = "sars-cov-2"
        ref_info = REFERENCE_SOURCES[ref_id]
        ref_dir = self.references_dir / ref_id
        ref_dir.mkdir(parents=True, exist_ok=True)
        
        fasta_path = ref_dir / "reference.fasta"
        
        logger.info("Bootstrapping SARS-CoV-2 reference", accession=ref_info["accession"])
        
        # Download reference genome
        if not self._download_file(
            ref_info["fasta_url"],
            fasta_path,
            f"SARS-CoV-2 reference ({ref_info['accession']})"
        ):
            return DatabaseInfo(
                name=ref_info["name"],
                version="unknown",
                status=DatabaseStatus.ERROR,
                error_message="Failed to download reference genome"
            )
        
        # Verify genome length
        with open(fasta_path) as f:
            content = f.read()
            seq_length = len("".join(content.split("\n")[1:]).replace("\n", ""))
        
        if seq_length != ref_info["expected_length"]:
            logger.warning(
                "Reference length mismatch",
                expected=ref_info["expected_length"],
                actual=seq_length
            )
        
        # Compute checksum
        checksum = self._compute_checksum(fasta_path)
        
        # Update manifest
        self.manifest["databases"][ref_id] = {
            "name": ref_info["name"],
            "version": ref_info["accession"],
            "accession": ref_info["accession"],
            "checksum": checksum,
            "length": seq_length,
            "installed_at": datetime.utcnow().isoformat(),
            "path": str(fasta_path),
        }
        self._save_manifest()
        
        logger.info(
            "SARS-CoV-2 reference installed",
            path=str(fasta_path),
            length=seq_length,
            checksum=checksum[:16] + "..."
        )
        
        return DatabaseInfo(
            name=ref_info["name"],
            version=ref_info["accession"],
            status=DatabaseStatus.INSTALLED,
            path=fasta_path,
            source_url=ref_info["fasta_url"],
            checksum=checksum,
            installed_at=datetime.utcnow(),
        )
    
    def bootstrap_primer_schemes(self) -> list[DatabaseInfo]:
        """
        Bootstrap ARTIC primer schemes.
        
        Downloads all known primer BED files from ARTIC Network GitHub.
        """
        primers_dir = self.references_dir / "primers"
        primers_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        
        for scheme_id, scheme_info in PRIMER_SCHEMES.items():
            bed_path = primers_dir / f"{scheme_id}.bed"
            
            logger.info("Downloading primer scheme", scheme=scheme_id)
            
            if self._download_file(
                scheme_info["url"],
                bed_path,
                f"Primer scheme {scheme_info['name']}"
            ):
                checksum = self._compute_checksum(bed_path)
                
                self.manifest["primers"][scheme_id] = {
                    "name": scheme_info["name"],
                    "checksum": checksum,
                    "installed_at": datetime.utcnow().isoformat(),
                    "path": str(bed_path),
                }
                
                results.append(DatabaseInfo(
                    name=scheme_info["name"],
                    version="latest",
                    status=DatabaseStatus.INSTALLED,
                    path=bed_path,
                    source_url=scheme_info["url"],
                    checksum=checksum,
                    installed_at=datetime.utcnow(),
                ))
            else:
                results.append(DatabaseInfo(
                    name=scheme_info["name"],
                    version="unknown",
                    status=DatabaseStatus.ERROR,
                    error_message=f"Failed to download from {scheme_info['url']}"
                ))
        
        self._save_manifest()
        return results
    
    def bootstrap_all(self) -> dict:
        """
        Bootstrap all required databases.
        
        Returns summary of installation results.
        """
        logger.info("Starting full database bootstrap")
        
        results = {
            "references": {},
            "primers": {},
            "success": True,
            "errors": [],
        }
        
        # Bootstrap SARS-CoV-2
        sars_result = self.bootstrap_sars_cov_2()
        results["references"]["sars-cov-2"] = sars_result.to_dict()
        if sars_result.status == DatabaseStatus.ERROR:
            results["success"] = False
            results["errors"].append(sars_result.error_message)
        
        # Bootstrap primer schemes
        primer_results = self.bootstrap_primer_schemes()
        for pr in primer_results:
            results["primers"][pr.name] = pr.to_dict()
            if pr.status == DatabaseStatus.ERROR:
                results["success"] = False
                results["errors"].append(pr.error_message)
        
        logger.info(
            "Database bootstrap complete",
            success=results["success"],
            error_count=len(results["errors"])
        )
        
        return results
    
    def get_reference_path(self, virus: str = "sars-cov-2") -> Optional[Path]:
        """Get path to reference genome."""
        ref_path = self.references_dir / virus / "reference.fasta"
        return ref_path if ref_path.exists() else None
    
    def get_primer_path(self, scheme: str) -> Optional[Path]:
        """Get path to primer scheme BED file."""
        # Normalize scheme name
        scheme_key = scheme.upper().replace("_", "-").replace("V", "-V")
        if not scheme_key.startswith("ARTIC-"):
            scheme_key = f"ARTIC-{scheme_key}"
        
        bed_path = self.references_dir / "primers" / f"{scheme_key}.bed"
        if bed_path.exists():
            return bed_path
        
        # Try alternative naming conventions
        for key in PRIMER_SCHEMES:
            if scheme.lower() in key.lower():
                alt_path = self.references_dir / "primers" / f"{key}.bed"
                if alt_path.exists():
                    return alt_path
        
        return None
    
    def verify_integrity(self) -> dict:
        """Verify integrity of all installed databases."""
        results = {"valid": True, "issues": []}
        
        for ref_id, ref_data in self.manifest.get("databases", {}).items():
            path = Path(ref_data.get("path", ""))
            if not path.exists():
                results["valid"] = False
                results["issues"].append(f"Missing file: {path}")
                continue
            
            checksum = self._compute_checksum(path)
            if checksum != ref_data.get("checksum"):
                results["valid"] = False
                results["issues"].append(f"Checksum mismatch: {ref_id}")
        
        for scheme_id, scheme_data in self.manifest.get("primers", {}).items():
            path = Path(scheme_data.get("path", ""))
            if not path.exists():
                results["valid"] = False
                results["issues"].append(f"Missing primer scheme: {path}")
        
        return results
