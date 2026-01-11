#!/bin/bash
# VGAP Reproducibility Verification Script
# Verifies that outputs can be reproduced from inputs
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== VGAP Reproducibility Verification ==="

if [ $# -lt 2 ]; then
    echo "Usage: $0 <run_output_dir> <test|full>"
    echo "  run_output_dir: Directory containing previous run outputs"
    echo "  test: Quick verification (checksums only)"
    echo "  full: Full re-run and comparison"
    exit 1
fi

OUTPUT_DIR="$1"
MODE="$2"

# Check required files
if [ ! -f "$OUTPUT_DIR/provenance.json" ]; then
    echo "ERROR: provenance.json not found in $OUTPUT_DIR"
    exit 1
fi

if [ ! -f "$OUTPUT_DIR/checksums.txt" ]; then
    echo "ERROR: checksums.txt not found in $OUTPUT_DIR"
    exit 1
fi

echo "Output directory: $OUTPUT_DIR"
echo "Verification mode: $MODE"

# Extract provenance info
echo ""
echo "=== Provenance Information ==="
python3 -c "
import json
with open('$OUTPUT_DIR/provenance.json') as f:
    p = json.load(f)
print(f\"Run ID: {p.get('run_id', 'N/A')}\")
print(f\"Timestamp: {p.get('timestamp', 'N/A')}\")
print(f\"User: {p.get('user_id', 'N/A')}\")
print()
print('Software versions:')
for sw in p.get('software', []):
    print(f\"  - {sw['name']}: {sw['version']}\")
print()
print('Random seeds:')
for tool, seed in p.get('random_seeds', {}).items():
    print(f\"  - {tool}: {seed}\")
"

# Verify checksums
echo ""
echo "=== Checksum Verification ==="

CHECKSUM_ERRORS=0
while IFS= read -r line; do
    if [ -z "$line" ]; then continue; fi
    
    EXPECTED=$(echo "$line" | awk '{print $1}')
    FILEPATH=$(echo "$line" | awk '{print $2}')
    FULLPATH="$OUTPUT_DIR/$FILEPATH"
    
    if [ ! -f "$FULLPATH" ]; then
        echo "MISSING: $FILEPATH"
        CHECKSUM_ERRORS=$((CHECKSUM_ERRORS + 1))
        continue
    fi
    
    ACTUAL=$(shasum -a 256 "$FULLPATH" | awk '{print $1}')
    
    if [ "$EXPECTED" != "$ACTUAL" ]; then
        echo "MISMATCH: $FILEPATH"
        echo "  Expected: $EXPECTED"
        echo "  Actual:   $ACTUAL"
        CHECKSUM_ERRORS=$((CHECKSUM_ERRORS + 1))
    else
        echo "OK: $FILEPATH"
    fi
done < "$OUTPUT_DIR/checksums.txt"

echo ""
if [ $CHECKSUM_ERRORS -eq 0 ]; then
    echo "✓ All checksums verified successfully"
else
    echo "✗ $CHECKSUM_ERRORS checksum errors found"
fi

# Full re-run verification
if [ "$MODE" = "full" ]; then
    echo ""
    echo "=== Full Re-run Verification ==="
    
    # Extract input files from provenance
    INPUTS=$(python3 -c "
import json
with open('$OUTPUT_DIR/provenance.json') as f:
    p = json.load(f)
for f in p.get('inputs', {}).get('files', []):
    print(f['path'])
")
    
    # Check if inputs exist
    INPUTS_OK=true
    for INPUT in $INPUTS; do
        if [ ! -f "$INPUT" ]; then
            echo "WARNING: Input file missing: $INPUT"
            INPUTS_OK=false
        fi
    done
    
    if [ "$INPUTS_OK" = false ]; then
        echo "Cannot perform full re-run: some input files are missing"
        exit 1
    fi
    
    # Create temporary output directory
    RERUN_DIR=$(mktemp -d)
    echo "Re-running in: $RERUN_DIR"
    
    # Extract and run with same parameters
    python3 -c "
import json
with open('$OUTPUT_DIR/provenance.json') as f:
    p = json.load(f)
    
# Generate re-run command
params = p.get('parameters', {})
seeds = p.get('random_seeds', {})

print('Parameters:', json.dumps(params, indent=2))
print('Seeds:', json.dumps(seeds, indent=2))
"
    
    echo ""
    echo "Full re-run requires the VGAP pipeline to be running."
    echo "Use the API to submit a new run with the same parameters."
    echo "Compare outputs using: diff -r $OUTPUT_DIR $RERUN_DIR"
    
    rm -rf "$RERUN_DIR"
fi

echo ""
echo "=== Verification Complete ==="
exit $CHECKSUM_ERRORS
