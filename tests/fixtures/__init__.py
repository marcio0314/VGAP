"""
VGAP Test Fixtures - Synthetic test datasets
"""

import gzip
from pathlib import Path

# Synthetic FASTQ data for testing
SYNTHETIC_R1 = """\
@SAMPLE001_read1/1
ATGTCTGATAATGGACCCCAAAATCAGCGAAATGCACCCCGCATTACGTTTGGTGGACCCTCAGATTCAACTGGCAGTAACCAGA
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
@SAMPLE001_read2/1
GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAG
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
@SAMPLE001_read3/1
TTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAGTTAG
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
"""

SYNTHETIC_R2 = """\
@SAMPLE001_read1/2
TGGTTACTGCCAGTTGAATCTGAGGGTCCACCAAACGTAATGCGGGGTGCATTTCGCTGATTTTGGGGTCCATTATCAGACAT
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
@SAMPLE001_read2/2
CTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
@SAMPLE001_read3/2
CTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAACTAA
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
"""

# SARS-CoV-2 reference (first 500bp for testing)
REFERENCE_FASTA = """\
>NC_045512.2 Severe acute respiratory syndrome coronavirus 2 isolate Wuhan-Hu-1
ATTAAAGGTTTATACCTTCCCAGGTAACAAACCAACCAACTTTCGATCTCTTGTAGATCTGTTCTCTAAA
CGAACTTTAAAATCTGTGTGGCTGTCACTCGGCTGCATGCTTAGTGCACTCACGCAGTATAATTAATAAC
TAATTACTGTCGTTGACAGGACACGAGTAACTCGTCTATCTTCTGCAGGCTGCTTACGGTTTCGTCCGTG
TTGCAGCCGATCATCAGCACATCTAGGTTTCGTCCGGGTGTGACCGAAAGGTAAGATGGAGAGCCTTGTC
CCTGGTTTCAACGAGAAAACACACGTCCAACTCAGTTTGCCTGTTTTACAGGTTCGCGACGTGCTCGTAC
GTGGCTTTGGAGACTCCGTGGAGGAGGTCTTATCAGAGGCACGTCAACATCTTAAAGATGGCACTTGTGG
CTTAGTAGAAGTTGAAAAAGGCGTTTTGCCTCAACTTGAACAGCCCTATGTGTTCATCAAACGTTCGGAT
GCTCGAACTGC
"""

# Sample metadata
SAMPLE_METADATA = {
    "sample_id": "TEST001",
    "collection_date": "2024-01-15",
    "host": "human",
    "location": "US",
    "protocol": "amplicon",
    "platform": "Illumina NovaSeq 6000",
    "run_id": "RUN20240115",
    "batch_id": "BATCH001",
    "is_control": False,
}

NEGATIVE_CONTROL_METADATA = {
    "sample_id": "NTC001",
    "collection_date": "2024-01-15",
    "host": "human",
    "location": "US",
    "protocol": "amplicon",
    "platform": "Illumina NovaSeq 6000",
    "run_id": "RUN20240115",
    "batch_id": "BATCH001",
    "is_control": True,
    "control_type": "negative",
}

# Expected outputs for regression testing
EXPECTED_OUTPUTS = {
    "TEST001": {
        "qc_pass": True,
        "read_count_range": (100, 1000),
        "variant_count_range": (0, 50),
        "lineage_pattern": r"^[A-Z]+(\.\d+)*$",
    }
}


def create_test_fixtures(output_dir: Path):
    """Create test fixture files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create FASTQ files
    r1_path = output_dir / "TEST001_R1.fastq.gz"
    r2_path = output_dir / "TEST001_R2.fastq.gz"
    
    with gzip.open(r1_path, 'wt') as f:
        f.write(SYNTHETIC_R1)
    
    with gzip.open(r2_path, 'wt') as f:
        f.write(SYNTHETIC_R2)
    
    # Create reference
    ref_path = output_dir / "reference.fasta"
    ref_path.write_text(REFERENCE_FASTA)
    
    # Create sample sheet
    import csv
    sample_sheet = output_dir / "samples.csv"
    with open(sample_sheet, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=SAMPLE_METADATA.keys())
        writer.writeheader()
        writer.writerow(SAMPLE_METADATA)
        writer.writerow(NEGATIVE_CONTROL_METADATA)
    
    return {
        "r1": r1_path,
        "r2": r2_path,
        "reference": ref_path,
        "sample_sheet": sample_sheet,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        output = Path(sys.argv[1])
    else:
        output = Path("tests/fixtures")
    
    files = create_test_fixtures(output)
    print(f"Created test fixtures in {output}")
    for name, path in files.items():
        print(f"  {name}: {path}")
