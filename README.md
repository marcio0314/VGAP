# VGAP - Viral Genomics Analysis Platform

[![CI](https://github.com/vgap/vgap/workflows/CI/badge.svg)](https://github.com/vgap/vgap/actions)
[![Coverage](https://codecov.io/gh/vgap/vgap/branch/main/graph/badge.svg)](https://codecov.io/gh/vgap/vgap)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade, end-to-end platform for viral genomics focused on RNA and DNA respiratory viruses using Illumina paired-end sequencing data.

## Features

- **Complete Pipeline**: From raw FASTQ to publication-ready reports
- **Multi-Virus Support**: SARS-CoV-2, Influenza, RSV, and other respiratory viruses
- **Dual Mode**: Amplicon (ARTIC/tiling) and Shotgun/Metagenomic pipelines
- **Variant Calling**: Consensus and intra-host minor variant detection
- **Lineage Assignment**: Pangolin, Nextclade, and influenza clade tools
- **Phylogenetics**: Multiple sequence alignment and tree construction
- **Scientific Rigor**: Full provenance, checksums, and reproducibility
- **Production Ready**: Docker, Kubernetes, monitoring, and audit logging

## Quick Start

### Prerequisites

- Docker and Docker Compose
- 8+ CPU cores, 64GB RAM recommended
- 100GB+ storage for references and results

### Installation

```bash
# Clone the repository
git clone https://github.com/vgap/vgap.git
cd vgap
```

### Easy Launch (macOS)

Double-click `start_vgap.command` to start the platform with:
- Automatic environment validation
- Real-time colorized logs
- Clean shutdown (Ctrl+C)

### Manual Start

```bash
# Start via Docker Compose
cd docker && docker compose up -d

# Or use the launcher script
./start_vgap.command
```

### Access Points

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **Grafana**: http://localhost:3000

### Running an Analysis

```bash
# Using the CLI
vgap run \
  --input-dir /path/to/fastq/ \
  --metadata samples.csv \
  --mode amplicon \
  --primer-scheme ARTIC_v4.1 \
  --output-dir /path/to/results/
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web UI / REST API                         │
├─────────────────────────────────────────────────────────────────┤
│                         Task Queue (Celery)                      │
├─────────────────────────────────────────────────────────────────┤
│  Pre-flight │   QC    │ Mapping │ Variants │ Lineage │ Phylo   │
├─────────────────────────────────────────────────────────────────┤
│  fastp │ minimap2 │ ivar │ bcftools │ pangolin │ IQ-TREE       │
├─────────────────────────────────────────────────────────────────┤
│                  PostgreSQL │ Redis │ File Storage              │
└─────────────────────────────────────────────────────────────────┘
```

## Pipeline Stages

1. **Pre-flight Validation**: FASTQ integrity, metadata validation, primer scheme checks
2. **Quality Control**: Adapter trimming (fastp), host removal, contamination checks
3. **Mapping/Assembly**: Reference mapping (minimap2), coverage metrics, consensus
4. **Variant Calling**: Amplicon-aware (ivar) and read-based (bcftools/LoFreq) calling
5. **Annotation**: Gene/codon mapping, amino acid changes, mutation flagging
6. **Lineage Assignment**: Pangolin, Nextclade, influenza clade assignment
7. **Phylogenetics**: MAFFT alignment, IQ-TREE construction, TreeTime dating
8. **Reporting**: Interactive HTML, PDF export, publication-quality figures

## Documentation

- [User Guide](docs/user-guide.md)
- [Admin Guide](docs/admin-guide.md)
- [Developer Guide](docs/developer-guide.md)
- [API Reference](docs/api-reference.md)

## Configuration

Configuration is via environment variables or `.env` file:

```bash
# Database
DATABASE_URL=postgresql://vgap:password@localhost:5432/vgap

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256

# Pipeline
MIN_DEPTH=10
MIN_ALLELE_FREQ=0.5
```

## Security

- TLS encryption for all network traffic
- JWT-based authentication with RBAC
- Audit logging of all sensitive operations
- No automatic external data uploads
- GISAID compliance: explicit user action required

## License

MIT License - see [LICENSE](LICENSE) for details.

## Citation

If you use VGAP in your research, please cite:

```bibtex
@software{vgap2024,
  title = {VGAP: Viral Genomics Analysis Platform},
  year = {2024},
  url = {https://github.com/vgap/vgap}
}
```
