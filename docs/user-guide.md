# VGAP User Guide

## Introduction

VGAP (Viral Genomics Analysis Platform) is a production-grade platform for analyzing respiratory virus genomes from Illumina paired-end sequencing data.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- 8+ CPU cores, 64GB RAM recommended
- 100GB+ storage

### Quick Start

```bash
# Clone the repository
git clone https://github.com/vgap/vgap.git
cd vgap

# Start all services
docker compose -f docker/docker-compose.yml up -d

# Access the web UI
open http://localhost:8080
```

## Preparing Your Data

### Input Files

VGAP accepts paired FASTQ files with Illumina naming conventions:
- `SAMPLE_R1.fastq.gz` and `SAMPLE_R2.fastq.gz`
- `SAMPLE_1.fastq.gz` and `SAMPLE_2.fastq.gz`

### Sample Sheet

Create a CSV file with sample metadata:

```csv
sample_id,collection_date,host,location,protocol,platform,run_id,batch_id
SAMPLE001,2024-01-15,human,US,amplicon,NovaSeq,RUN001,BATCH001
SAMPLE002,2024-01-16,human,UK,amplicon,NovaSeq,RUN001,BATCH001
```

Required fields:
- `sample_id`: Unique identifier
- `collection_date`: YYYY-MM-DD format
- `host`: human, animal, or environmental
- `location`: Country or region (ISO code preferred)
- `protocol`: amplicon, shotgun, or capture
- `platform`: Illumina instrument model
- `run_id`: Sequencing run identifier
- `batch_id`: Processing batch

## Running an Analysis

### Using the Web UI

1. Navigate to **Projects** → **New Run**
2. Upload your FASTQ files
3. Upload or enter sample metadata
4. Select pipeline mode:
   - **Amplicon**: For tiled amplicon data (ARTIC, midnight, etc.)
   - **Shotgun**: For metagenomic or capture data
5. Configure parameters (or use defaults)
6. Click **Start Analysis**

### Using the API

```bash
# Create a run
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Analysis",
    "mode": "amplicon",
    "primer_scheme": "ARTIC_v4.1",
    "samples": [...]
  }'
```

## Understanding Results

### QC Metrics

| Metric | Good | Warning | Fail |
|--------|------|---------|------|
| Q30 Rate | >80% | 50-80% | <50% |
| Mapping Rate | >90% | 70-90% | <70% |
| Coverage 10× | >95% | 80-95% | <80% |

### Variant Classification

- **Consensus variants**: Allele frequency ≥50%
- **Minor variants**: Allele frequency 2-50%
- **Flagged mutations**: Known variants of concern

### Lineage Assignment

For SARS-CoV-2:
- Pango lineage (e.g., BA.2.86)
- Nextclade clade (e.g., 23I)
- Confidence score

## Downloading Results

All outputs are available via the web UI or API:

- `consensus.fasta` - Consensus sequences
- `variants.vcf` - Called variants
- `variants.tsv` - Annotated variant table
- `coverage.bed` - Per-position depth
- `lineage.tsv` - Lineage assignments
- `tree.nwk` - Phylogenetic tree
- `report.html` - Full analysis report
- `provenance.json` - Complete run provenance

## Troubleshooting

### Run Failed During Validation

Check the error message for specific issues:
- **FASTQ_CORRUPT_GZIP**: Re-download the FASTQ files
- **PAIR_ID_MISMATCH**: Ensure R1 and R2 files match
- **METADATA_MISSING_FIELD**: Add required metadata fields

### Low Coverage

Possible causes:
- Low input DNA/RNA
- Poor library quality
- Wrong reference genome
- Host contamination (check host removal stats)

### Lineage Assignment Failed

Ensure:
- Consensus sequence has <50% Ns
- Reference is correct for the virus type
- Lineage databases are up to date (admin action)
