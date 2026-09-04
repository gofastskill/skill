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
# Naming a suite runs only that one. CI does this to put each suite on its own runner --
# 42 cases at trials=5 is ~6.3h sequentially, past GitHub's hard 6h per-job ceiling, and the
# suites share nothing until the scorecard. A subset run deliberately does NOT score itself:
# the metrics in metrics.toml span all three suites, and a metric matching no case is a hard
# error (EVAL_SCORECARD_EMPTY_METRIC), so scoring `restraint` alone would fail on the two
# judge_score metrics rather than tell you anything. Fold the parts with scorecard.sh instead.
#
# Usage: run.sh <agent> <out-dir> [trials] [suite...]
set -euo pipefail

AGENT="${1:?usage: run.sh <agent> <out-dir> [trials] [suite...]}"
OUT="${2:?usage: run.sh <agent> <out-dir> [trials] [suite...]}"
TRIALS="${3:-5}"
shift $(( $# < 3 ? $# : 3 ))

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

all_suites=(consultation restraint correctness)

# No suite named => the full sweep, which scores itself. Any subset => the caller is
# assembling a sweep out of parts and scorecard.sh is what has the opinion.
if (($#)); then
  suites=("$@")
  for suite in "${suites[@]}"; do
    if [[ ! -d "$HERE/$suite" ]]; then
      echo "no such suite: '$suite' (have: ${all_suites[*]})" >&2
      exit 2
    fi
  done
  score_at_end=0
else
  suites=("${all_suites[@]}")
  score_at_end=1
fi

# Anchor OUT before anything derives from it. Every suite below runs from inside a throwaway
# skill tree staged elsewhere (stage.sh), so a relative out-dir resolves against *that* tree
# rather than the caller's cwd: the run lands somewhere unrelated and the log redirect fails
# outright. Symptom when this is missing -- "<out-dir>/<suite>.log: No such file or directory",
# one RUNNER ERROR per suite, then EVAL_SCORECARD_NO_RUNS from a scorecard with nothing to read.
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
STAGE="$OUT/.stage"

mkdir -p "$STAGE"

# The guard is a precondition, not a formality: without it the numbers are meaningless.
echo "=== vacuity guard ==="
python3 "$HERE/guard_vacuity.py"
echo

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
  # The gates live in metrics.toml and are applied once, by scorecard.sh, over all three.
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

if ((score_at_end)); then
  echo
  exec "$HERE/scorecard.sh" "$OUT"
fi

echo
echo "=== ran ${#suites[@]} of ${#all_suites[@]} suite(s); not scoring a subset ==="
echo "fold this with the others: $HERE/scorecard.sh <dir containing all three>"
