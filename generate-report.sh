#!/usr/bin/env bash
# generate-report.sh — Parse latest benchmark results and produce the DD appendix
# Usage: ./generate-report.sh [results-dir]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${1:-$SCRIPT_DIR/results}"

# Find the most recent summary file
SUMMARY=$(ls -t "$RESULTS_DIR"/*-summary.md 2>/dev/null | head -1)
if [ -z "$SUMMARY" ]; then
    echo "No summary file found in $RESULTS_DIR" >&2
    exit 1
fi

TIMESTAMP=$(basename "$SUMMARY" -summary.md)
DATE=$(echo "$TIMESTAMP" | cut -c1-10 | tr - /)

echo "=== Generating report from: $SUMMARY ==="
echo ""

# Output the full report to stdout (caller can redirect to DD file)
cat "$SUMMARY"
