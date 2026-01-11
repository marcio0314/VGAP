"""
VGAP Provenance Module - Track all inputs, outputs, and parameters.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


@dataclass
class ProvenanceCollector:
    """Collects provenance information during pipeline execution."""
    
    run_id: UUID = field(default_factory=uuid4)
    user_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    inputs: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    software: list[dict[str, str]] = field(default_factory=list)
    databases: list[dict[str, str]] = field(default_factory=list)
    commands: list[dict[str, Any]] = field(default_factory=list)
    random_seeds: dict[str, int] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    validation_status: dict[str, str] = field(default_factory=dict)
    
    def add_input_file(self, path: Path, category: str = "input"):
        """Record an input file with checksum."""
        if path.exists():
            checksum = self._compute_checksum(path)
            size = path.stat().st_size
        else:
            checksum = ""
            size = 0
        
        if "files" not in self.inputs:
            self.inputs["files"] = []
        
        self.inputs["files"].append({
            "path": str(path),
            "sha256": checksum,
            "size_bytes": size,
            "category": category,
        })
    
    def add_software(self, name: str, version: str, container: str = None):
        """Record software version."""
        entry = {"name": name, "version": version}
        if container:
            entry["container"] = container
        
        # Avoid duplicates
        for s in self.software:
            if s["name"] == name:
                s.update(entry)
                return
        
        self.software.append(entry)
    
    def add_database(self, name: str, version: str, checksum: str = ""):
        """Record database version."""
        self.databases.append({
            "name": name,
            "version": version,
            "checksum": checksum,
        })
    
    def add_command(self, name: str, cmd: list[str]):
        """Record executed command."""
        self.commands.append({
            "name": name,
            "command": " ".join(str(c) for c in cmd),
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def add_output_file(self, path: Path, name: str = None):
        """Record output file with checksum."""
        name = name or path.stem
        if path.exists():
            self.outputs[name] = self._compute_checksum(path)
    
    def set_seed(self, tool: str, seed: int):
        """Record random seed for reproducibility."""
        self.random_seeds[tool] = seed
    
    def set_validation(self, stage: str, status: str):
        """Record validation status."""
        self.validation_status[stage] = status
    
    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum."""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def to_dict(self) -> dict[str, Any]:
        """Export provenance as dictionary."""
        return {
            "run_id": str(self.run_id),
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "inputs": self.inputs,
            "parameters": self.parameters,
            "software": self.software,
            "databases": self.databases,
            "commands": self.commands,
            "random_seeds": self.random_seeds,
            "outputs": self.outputs,
            "validation_status": self.validation_status,
        }
    
    def save(self, path: Path):
        """Save provenance to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "ProvenanceCollector":
        """Load provenance from JSON file."""
        with open(path) as f:
            data = json.load(f)
        
        p = cls()
        p.run_id = UUID(data["run_id"])
        p.timestamp = datetime.fromisoformat(data["timestamp"])
        p.user_id = data.get("user_id", "")
        p.inputs = data.get("inputs", {})
        p.parameters = data.get("parameters", {})
        p.software = data.get("software", [])
        p.databases = data.get("databases", [])
        p.commands = data.get("commands", [])
        p.random_seeds = data.get("random_seeds", {})
        p.outputs = data.get("outputs", {})
        p.validation_status = data.get("validation_status", {})
        return p


def generate_checksums_file(output_dir: Path) -> Path:
    """Generate checksums.txt for all output files."""
    checksums_path = output_dir / "checksums.txt"
    
    with open(checksums_path, 'w') as f:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file() and path != checksums_path:
                sha256 = hashlib.sha256()
                with open(path, 'rb') as pf:
                    for chunk in iter(lambda: pf.read(65536), b''):
                        sha256.update(chunk)
                
                rel_path = path.relative_to(output_dir)
                f.write(f"{sha256.hexdigest()}  {rel_path}\n")
    
    return checksums_path


def verify_checksums(output_dir: Path) -> tuple[bool, list[str]]:
    """Verify checksums.txt against actual files."""
    checksums_path = output_dir / "checksums.txt"
    if not checksums_path.exists():
        return False, ["checksums.txt not found"]
    
    errors = []
    with open(checksums_path) as f:
        for line in f:
            parts = line.strip().split("  ", 1)
            if len(parts) != 2:
                continue
            
            expected, rel_path = parts
            path = output_dir / rel_path
            
            if not path.exists():
                errors.append(f"Missing: {rel_path}")
                continue
            
            sha256 = hashlib.sha256()
            with open(path, 'rb') as pf:
                for chunk in iter(lambda: pf.read(65536), b''):
                    sha256.update(chunk)
            
            if sha256.hexdigest() != expected:
                errors.append(f"Mismatch: {rel_path}")
    
    return len(errors) == 0, errors
