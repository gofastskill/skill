#!/usr/bin/env bash
# Negative control for the consultation check (spec 001 §8 step 3).
#
# Takes a real completed consultation case, makes two copies, and deletes from one of them
# every trace line naming the staged skill path -- i.e. simulates an agent that answered
# without ever opening the skill. Re-scores both with the engine's own scorer. The check is
# load-bearing only if PRESENT passes and ABSENT fails.
#
# `skill_invoked` matches the skill document's path against the input of any tool use (R8),
# and the path it matches is the one the run recorded per trial. So the mutation pattern is
# read from the artifacts, not from patterns.json: the control has to delete the evidence
# the check actually reads, not a string that resembles it.
#
# Usage: evals/v2/negctl.sh <consultation-run-dir> [case-id]
#   <consultation-run-dir> is the .../<timestamp>/<agent> directory of a real run.
set -euo pipefail

RUN_DIR=${1:?usage: negctl.sh <consultation-run-dir> [case-id]}
CASE=${2:-}
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

if [ -z "$CASE" ]; then
  CASE=$(find "$RUN_DIR" -mindepth 1 -maxdepth 1 -type d -name 'op-*' -printf '%f\n' | sort | head -1)
fi
SRC="$RUN_DIR/$CASE"
[ -d "$SRC" ] || { echo "no such case dir: $SRC" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

PATTERN=$(python3 - "$SRC" <<'PY'
import json, pathlib, sys
src = pathlib.Path(sys.argv[1])
paths = set()
for r in sorted(src.glob("trial-*/result.json")):
    p = json.loads(r.read_text()).get("skill_path")
    if p:
        paths.add(p)
if not paths:
    sys.exit(
        "this run recorded no skill_path, so there is nothing for skill_invoked to match "
        "and the control cannot prove anything. Re-run the suite with a build that records "
        "it (R5) and try again."
    )
if len(paths) > 1:
    sys.exit(f"trials disagree on the staged skill path, refusing to guess: {sorted(paths)}")
print(paths.pop())
PY
)

python3 - "$SRC" "$WORK" "$CASE" "$PATTERN" "$ROOT" <<'PY'
import json, pathlib, shutil, sys
src, work, case, pattern, root = sys.argv[1:6]
iso = json.load(open(pathlib.Path(root, "evals/fixtures/pass/summary.json")))["isolation"]
n_trials = len(list(pathlib.Path(src).glob("trial-*")))
for variant in ("present", "absent"):
    dst = pathlib.Path(work, variant, case)
    shutil.copytree(src, dst)
    if variant == "absent":
        for t in sorted(dst.glob("trial-*/trace.jsonl")):
            lines = t.read_text().splitlines()
            kept = [l for l in lines if pattern not in l]
            removed = len(lines) - len(kept)
            print(f"  {variant}/{t.parent.name}: removed {removed} line(s)")
            if removed == 0:
                sys.exit(
                    f"{t}: no trace line names the skill path, so the 'absent' variant is "
                    "identical to 'present' and the control would pass without testing "
                    "anything. Pick a case whose trials did consult the skill."
                )
            t.write_text("\n".join(kept) + "\n")
    trials = [{"trial_id": i, "status": "passed", "command_count": None,
               "input_tokens": None, "output_tokens": None,
               "check_results": [], "error_message": None}
              for i in range(1, n_trials + 1)]
    # should_trigger drives the generated skill_invoked check (R7); without it the
    # re-score falls back to the explicit checks alone and measures nothing here.
    pathlib.Path(work, variant, "summary.json").write_text(json.dumps({
        "suite_pass": True, "suite_pass_rate": 1.0, "agent": "pi", "model": "",
        "total_cases": 1, "passed": 1, "failed": 0,
        "trials_per_case": n_trials, "parallel": n_trials, "pass_threshold": 1.0,
        "run_dir": str(pathlib.Path(work, variant)),
        "checks_path": "evals/v2/consultation/checks.toml",
        "skill_project_root": ".", "isolation": iso,
        "cases": [{"id": case, "status": "passed", "command_count": 0,
                   "input_tokens": 0, "output_tokens": 0, "pass_count": n_trials,
                   "total_trials": n_trials, "pass_rate": 1.0,
                   "should_trigger": True, "trials": trials}],
    }, indent=2))
PY

echo
echo "case: $CASE"
echo "path: $PATTERN"
rc=0
for v in present absent; do
  out=$(cd "$ROOT" && fastskill eval score --run-dir "$WORK/$v" --no-fail --json 2>&1)
  line=$(printf '%s' "$out" | python3 -c "
import json,sys
d=json.loads(sys.stdin.read()); c=d['cases'][0]
chk=[(t['check_name'],t['passed']) for t in c['trials'][0]['check_results']]
print('%s %.2f %s' % (c['status'], c['pass_rate'], chk))
")
  printf '  %-8s %s\n' "$v" "$line"
  case "$v:$line" in
    present:passed*) ;;
    absent:failed*) ;;
    *) rc=1 ;;
  esac
done

echo
if [ "$rc" -eq 0 ]; then
  echo "PASS: the consultation check discriminates -- it passes on a real"
  echo "      consultation trace and fails when the skill read is removed."
else
  echo "FAIL: the check did not flip. It is not measuring skill consultation."
fi
exit "$rc"
