#!/usr/bin/env bash
# Stage one spec-001 suite as a throwaway skill tree, and print where it landed.
#
# `eval run` and `eval validate` both read the suite paths from
# [tool.fastskill.eval] in the manifest and neither takes a flag to override them
# (spec 001 C5). So a suite is measured by copying the shipped skill somewhere
# disposable, beside a manifest that points at that suite. The tracked
# fastskill/skill-project.toml is never touched.
#
# The sweep and CI stage the same way, through this script, so the tree CI
# validates is the tree run.sh measures.
#
# Usage: stage.sh <suite> <dest-dir> [trials]
set -euo pipefail

SUITE="${1:?usage: stage.sh <suite> <dest-dir> [trials]}"
DEST="${2:?usage: stage.sh <suite> <dest-dir> [trials]}"
TRIALS="${3:-5}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$(cd "$HERE/../.." && pwd)/fastskill"

if [[ ! -d "$HERE/$SUITE" ]]; then
  echo "stage.sh: no suite '$SUITE' at $HERE/$SUITE" >&2
  exit 1
fi

rm -rf "$DEST"
mkdir -p "$DEST/evals"
cp -r "$SKILL_SRC" "$DEST/fastskill"

# The whole suite directory, not just the two files the engine always reads: a
# `[[judge]]` names its prompt relative to checks.toml, so the prompt has to land
# beside it.
cp "$HERE/$SUITE"/* "$DEST/evals/"

# Rebuild the manifest's eval section; keep everything above it byte-identical so
# the staged skill is the shipped skill.
python3 - "$SKILL_SRC/skill-project.toml" "$DEST/fastskill/skill-project.toml" "$TRIALS" <<'PY'
import sys
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

echo "$DEST/fastskill"
