#!/usr/bin/env bash
# Re-score copies of real evidence; no model calls, original artifacts unchanged.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/negctl.py" "$@"
