#!/usr/bin/env bash
# Run every spec-001 suite against one agent, then fold the runs into the metrics.
#
# Each suite gets a throwaway skill tree staged outside the repo by stage.sh, which is also
# what CI validates through — see that script for why staging is necessary at all.
#
# A suite whose checks.toml declares a `[[judge]]` is run with `--judge`, which calls an LLM
# once per trial. That needs two variables, checked up front rather than three suites in:
#
#   AIKIT_LLM_URL   the OpenAI-compatible endpoint that serves the judge model
#   JUDGE_API_KEY   its key — the `api_key_env` the judge's checks.toml names
#   JUDGE_MODEL     optional; overrides the model every judge declares. The committed default
#                   is a placeholder and has to exist on whatever AIKIT_LLM_URL serves.
#
# Usage: run.sh <agent> <out-dir> [trials]
set -euo pipefail

AGENT="${1:?usage: run.sh <agent> <out-dir> [trials]}"
OUT="${2:?usage: run.sh <agent> <out-dir> [trials]}"
TRIALS="${3:-5}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGE="$OUT/.stage"

mkdir -p "$OUT" "$STAGE"

# The guard is a precondition, not a formality: without it the numbers are meaningless.
echo "=== vacuity guard ==="
python3 "$HERE/guard_vacuity.py"
echo

suites=(consultation restraint correctness)

# Which suites are judged, decided before anything runs. correctness is last, so a missing
# key found at its turn would surface only after the other two had been paid for in full.
judged=()
for suite in "${suites[@]}"; do
  if grep -q '^\[\[judge\]\]' "$HERE/$suite/checks.toml"; then judged+=("$suite"); fi
done
judge_model=()
if ((${#judged[@]})); then
  : "${AIKIT_LLM_URL:?${judged[*]}: a judge needs an endpoint — set AIKIT_LLM_URL}"
  : "${JUDGE_API_KEY:?${judged[*]}: a judge needs a key — set JUDGE_API_KEY}"
  if [[ -n "${JUDGE_MODEL:-}" ]]; then judge_model=(--judge-model "$JUDGE_MODEL"); fi
  echo "=== judged suite(s): ${judged[*]} (endpoint $AIKIT_LLM_URL) ==="
  echo
fi

echo "=== running ${#suites[@]} suite(s) against '$AGENT', $TRIALS trial(s) per case ==="
for suite in "${suites[@]}"; do
  skill_dir="$("$HERE/stage.sh" "$suite" "$STAGE/$suite" "$TRIALS" | tail -1)"

  judge=()
  if grep -q '^\[\[judge\]\]' "$HERE/$suite/checks.toml"; then
    judge=(--judge "${judge_model[@]}")
  fi

  printf '  %-14s ' "$suite"
  # --no-fail: this is a measurement, not a gate (spec 001 P6). A failing case is data.
  # The gates live in metrics.toml and are applied once, below, over all three runs.
  if (cd "$skill_dir" && fastskill eval run \
        --agent "$AGENT" \
        --output-dir "$OUT/$suite" \
        "${judge[@]}" \
        --no-fail >"$OUT/$suite.log" 2>&1); then
    tail -3 "$OUT/$suite.log" | grep -oE '[0-9]+/[0-9]+ passed' | tail -1 || echo "done"
  else
    echo "RUNNER ERROR (see $OUT/$suite.log)"
  fi
done

echo
echo "=== scorecard ==="
# Exit status is the scorecard's: a gate below its bar, or a metric that matched no case,
# fails this script. That is the one place the sweep is allowed to have an opinion.
#
# The two `judge_score` metrics are the reason `--judge` above is not optional in practice: a
# metric that matches nothing is a hard error, so an unjudged correctness run fails here.
fastskill eval scorecard --root "$OUT" --metrics "$HERE/metrics.toml"
