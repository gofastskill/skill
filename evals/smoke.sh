#!/usr/bin/env bash
# Six cases, one trial, no native judge. Agent authentication is still required.
# Usage: bash evals/smoke.sh <agent> <new-output-dir> [model]
set -euo pipefail
AGENT="${1:?usage: smoke.sh <agent> <new-output-dir> [model]}"
OUT="${2:?usage: smoke.sh <agent> <new-output-dir> [model]}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Atomic creation refuses existing directories, files and symlinks.
mkdir -- "$OUT"
OUT="$(cd "$OUT" && pwd)"
python3 "$HERE/v2/guard_vacuity.py"
skill_dir="$(bash "$HERE/v2/stage.sh" smoke "$OUT/project" 1)"
model=()
if [[ -n "${3:-}" ]]; then model=(--model "$3"); fi
cd "$skill_dir"
fastskill eval validate --agent "$AGENT"
echo "Smoke only: consultation, restraint, tool budget and trace fragments; NOT semantic accuracy."
echo "Artifacts and staged project are retained in $OUT"
fastskill eval run --agent "$AGENT" --trials 1 "${model[@]}" --output-dir "$OUT/results"
