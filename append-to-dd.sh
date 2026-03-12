#!/usr/bin/env bash
# append-to-dd.sh — Append benchmark results to DD-038
# Usage: ./append-to-dd.sh [results-dir]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${1:-$SCRIPT_DIR/results}"
DD_FILE="$HOME/repos/ntnt/design-docs/dd-038-language-benchmarks.md"

# Find most recent summary
SUMMARY=$(ls -t "$RESULTS_DIR"/*-summary.md 2>/dev/null | head -1)
RAW_DIR="$RESULTS_DIR"

if [ -z "$SUMMARY" ]; then
    echo "No results found in $RESULTS_DIR" >&2
    exit 1
fi

TIMESTAMP=$(basename "$SUMMARY" -summary.md)
RUN_DATE=$(echo "$TIMESTAMP" | cut -c1-8 | sed 's/\(....\)\(..\)\(..\)/\1-\2-\3/')

echo "Appending results from $SUMMARY to $DD_FILE"

# Count raw files for proof
RAW_COUNT=$(ls "$RAW_DIR"/raw-*.txt 2>/dev/null | wc -l)

# Build the appendix
APPENDIX=$(cat << APPENDIX_END

---

## Benchmark Results — $RUN_DATE

> **Raw data:** $RAW_COUNT wrk output files saved in \`results/\`  
> **Repo:** [ntntlang/ntnt-benchmarks](https://github.com/ntntlang/ntnt-benchmarks) — reproduce with \`./benchmark.sh\`

$(cat "$SUMMARY")

### Raw File Index

\`\`\`
$(ls "$RAW_DIR"/raw-*.txt 2>/dev/null | xargs -I{} basename {} | sort)
\`\`\`

*Each file contains the full wrk output including latency histogram, socket errors, and per-second throughput. See the benchmarks repo for reproduction instructions.*
APPENDIX_END
)

# Check if results section already exists
if grep -q "## Benchmark Results" "$DD_FILE" 2>/dev/null; then
    echo "Results section already exists — removing old one first"
    # Remove everything from "## Benchmark Results" to end of file
    sed -i '/^---$/{N;/\n## Benchmark Results/,${d}}' "$DD_FILE"
fi

# Append
echo "$APPENDIX" >> "$DD_FILE"
echo "Done — results appended to $DD_FILE"
