#!/usr/bin/env bash
# Run every spec-001 suite against one agent and collect the artifacts.
#
# `eval run` has no flag to override the suite paths (spec 001 C5) — they come from
# [tool.fastskill.eval] in the manifest. So each suite gets a throwaway skill tree staged
# outside the repo, with a manifest pointing at that suite. The tracked
# fastskill/skill-project.toml is never touched.
#
# Usage: run.sh <agent> <out-dir> [trials]
set -euo pipefail

AGENT="${1:?usage: run.sh <agent> <out-dir> [trials]}"
OUT="${2:?usage: run.sh <agent> <out-dir> [trials]}"
TRIALS="${3:-5}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SKILL_SRC="$REPO/fastskill"
STAGE="$OUT/.stage"

mkdir -p "$OUT" "$STAGE"

# The guard is a precondition, not a formality: without it the numbers are meaningless.
echo "=== vacuity guard ==="
python3 "$HERE/guard_vacuity.py"
echo

suites=(consultation restraint)
while IFS= read -r d; do suites+=("correctness/$(basename "$d")"); done \
  < <(find "$HERE/correctness" -mindepth 1 -maxdepth 1 -type d | sort)

echo "=== running ${#suites[@]} suite(s) against '$AGENT', $TRIALS trial(s) per case ==="
for suite in "${suites[@]}"; do
  slug="${suite//\//-}"
  work="$STAGE/$slug"
  rm -rf "$work"
  mkdir -p "$work/evals"

  cp -r "$SKILL_SRC" "$work/fastskill"
  cp "$HERE/$suite/prompts.csv" "$HERE/$suite/checks.toml" "$work/evals/"

  # Rebuild the manifest's eval section; keep everything above it byte-identical so the
  # staged skill is the shipped skill.
  python3 - "$SKILL_SRC/skill-project.toml" "$work/fastskill/skill-project.toml" "$TRIALS" <<'PY'
import re, sys
src, dst, trials = sys.argv[1], sys.argv[2], int(sys.argv[3])
text = open(src, encoding="utf-8").read()
head = text.split("[tool.fastskill.eval]")[0].rstrip() + "\n"
open(dst, "w", encoding="utf-8").write(
    head
    + "\n[tool.fastskill.eval]\n"
      'prompts = "../evals/prompts.csv"\n'
      'checks  = "../evals/checks.toml"\n'
      "timeout_seconds = 300\n"
      f"trials_per_case = {trials}\n"
      f"parallel = {trials}\n"
      "pass_threshold = 1.0\n"
      "fail_on_missing_agent = true\n"
)
PY

  printf '  %-34s ' "$suite"
  # --no-fail: this is a measurement, not a gate (spec 001 P6). A failing case is data.
  if (cd "$work/fastskill" && fastskill eval run \
        --agent "$AGENT" \
        --output-dir "$OUT/$slug" \
        --no-fail >"$OUT/$slug.log" 2>&1); then
    tail -3 "$OUT/$slug.log" | grep -oE '[0-9]+/[0-9]+ passed' | tail -1 || echo "done"
  else
    echo "RUNNER ERROR (see $OUT/$slug.log)"
  fi
done

echo
echo "artifacts: $OUT"
