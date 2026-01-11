#!/bin/bash
# Tool verification script for VGAP bioinformatics container
# Verifies all tools are installed and reports versions

set -e

echo "========================================"
echo "VGAP Bioinformatics Tool Verification"
echo "========================================"
echo ""

ERRORS=0

verify_tool() {
    local name=$1
    local cmd=$2
    
    if command -v "$cmd" &> /dev/null; then
        version=$($3 2>&1 | head -n1 || true)
        echo "✓ $name: $version"
    else
        echo "✗ $name: NOT FOUND"
        ERRORS=$((ERRORS + 1))
    fi
}

echo "Core Tools:"
echo "-----------"
verify_tool "fastp" "fastp" "fastp --version"
verify_tool "samtools" "samtools" "samtools --version"
verify_tool "bcftools" "bcftools" "bcftools --version"
verify_tool "minimap2" "minimap2" "minimap2 --version"
verify_tool "bwa-mem2" "bwa-mem2" "bwa-mem2 version"
verify_tool "ivar" "ivar" "ivar version"
verify_tool "lofreq" "lofreq" "lofreq version"

echo ""
echo "Alignment & Phylogenetics:"
echo "--------------------------"
verify_tool "mafft" "mafft" "mafft --version"
verify_tool "iqtree2" "iqtree2" "iqtree2 --version"

echo ""
echo "Assembly Tools:"
echo "---------------"
verify_tool "spades.py" "spades.py" "spades.py --version"
verify_tool "megahit" "megahit" "megahit --version"

echo ""
echo "Python Packages:"
echo "----------------"
python3 -c "import Bio; print(f'✓ biopython: {Bio.__version__}')" || echo "✗ biopython: NOT FOUND"
python3 -c "import pysam; print(f'✓ pysam: {pysam.__version__}')" || echo "✗ pysam: NOT FOUND"
python3 -c "import pandas; print(f'✓ pandas: {pandas.__version__}')" || echo "✗ pandas: NOT FOUND"
python3 -c "import numpy; print(f'✓ numpy: {numpy.__version__}')" || echo "✗ numpy: NOT FOUND"

echo ""
echo "========================================"
if [ $ERRORS -eq 0 ]; then
    echo "All tools verified successfully!"
    exit 0
else
    echo "ERRORS: $ERRORS tools not found"
    exit 1
fi
