#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Python owns validation, atomic JSON, bounded prep and session-scoped cleanup.
exec "${PYTHON_BIN:-python3}" "$SCRIPT_DIR/scripts/http_benchmarks.py" "$@"
