#!/usr/bin/env bash
# Fold one or more spec-001 suite runs into the metrics and apply the gates.
#
# This is the one place the sweep is allowed to have an opinion: the exit status is the
# scorecard's, so a gate below its bar -- or a metric that matched no case -- fails here.
#
# It is a separate script from run.sh because CI runs the suites on three parallel runners
# (42 cases at trials=5 is ~6.3h sequentially, past GitHub's hard 6h per-job ceiling) and
# only reassembles them at the end. Scoring therefore has to be callable against a directory
# nothing in this job produced.
#
# The layout it expects is exactly what run.sh writes -- one directory per suite:
#
#   <root>/consultation/<timestamp>/<agent>/<case>/...
#   <root>/restraint/...
#   <root>/correctness/...
#
# Usage: scorecard.sh <root>
set -euo pipefail

ROOT="${1:?usage: scorecard.sh <root>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -d "$ROOT" ]] || { echo "no such directory: $ROOT" >&2; exit 2; }
ROOT="$(cd "$ROOT" && pwd)"

# metrics.toml spans all three suites and a metric that matches nothing is a hard error
# (EVAL_SCORECARD_EMPTY_METRIC). When a suite's runner failed outright its directory is
# simply absent, and the scorecard's own error names a metric rather than the missing
# suite -- which reads as a metrics.toml bug and is not one. Say which suite is missing.
missing=()
for suite in consultation restraint correctness; do
  [[ -d "$ROOT/$suite" ]] || missing+=("$suite")
done
if ((${#missing[@]})); then
  echo "::error::cannot score: no run directory for ${missing[*]} under $ROOT."
  echo "Every metric in metrics.toml is scoped to a case prefix from one of the three suites," >&2
  echo "so a missing suite surfaces here as EVAL_SCORECARD_EMPTY_METRIC naming the metric" >&2
  echo "rather than the gap. Check whether that suite's job ran and uploaded its artifact." >&2
  echo "present:" >&2
  find "$ROOT" -mindepth 1 -maxdepth 1 -type d -printf '  %f\n' 2>/dev/null | sort >&2 || true
  exit 1
fi

echo "=== scorecard ==="
fastskill eval scorecard --root "$ROOT" --metrics "$HERE/metrics.toml"
