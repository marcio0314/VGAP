# VGAP - Viral Genomics Analysis Platform

[![CI](https://github.com/marcio0314/VGAP/workflows/CI/badge.svg)](https://github.com/marcio0314/VGAP/actions)
[![Coverage](https://codecov.io/gh/marcio0314/VGAP/branch/main/graph/badge.svg)](https://codecov.io/gh/marcio0314/VGAP)

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

### Local Development Mode

**Note:** This version is configured for local scientific use. Authentication is disabled by default for ease of use. A default `admin` user is automatically provisioned.

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
- **Web UI**: http://localhost:3001
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

## Key Features

- **No-Auth Local Mode**: Frictionless local development and usage
- **Master Cleanup**: One-click system maintenance via Admin UI
- **Run Persistence**: Robust state management even if infrastructure restarts

## Documentation

- [User Guide](docs/user-guide.md)
- [Admin Guide](docs/admin-guide.md)
- [Developer Guide](docs/developer-guide.md)
- [API Reference](docs/api-reference.md)

## Security

- **Local Mode**: Authentication disabled for convenience. Do not expose to public internet.
- **Audit Logging**: All operations are logged for reproducibility
- **Data Safety**: Master Cleanup protects critical scientific data

## Author

**Marcio De Avila Arias, PhD**

## Copyright

Copyright (c) 2026 Marcio De Avila Arias, PhD. All rights reserved.

This software is proprietary. Unauthorized copying, modification, distribution, or use of this software is strictly prohibited without prior written permission from the author.

## Citation

If you use VGAP in your research, please cite:

```bibtex
@software{vgap2026,
  author = {De Avila Arias, Marcio},
  title = {VGAP: Viral Genomics Analysis Platform},
  year = {2026},
  url = {https://github.com/marcio0314/VGAP}
}
```
