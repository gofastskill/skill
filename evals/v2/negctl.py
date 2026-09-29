"""Consultation-only negative control; preserve recorded metadata per trial."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def remove_consultation(events, skill_path):
    removed = set()
    for event in events:
        payload = event.get("payload", {})
        if payload.get("type") != "tool_use":
            continue
        inputs = payload.get("input", {})
        named = (payload.get("tool_name", "").lower() == "skill" and
                 isinstance(inputs, dict) and any(inputs.get(key) == "fastskill"
                                                 for key in ("skill", "name", "skill_name")))
        referenced = bool(skill_path and skill_path in json.dumps(inputs))
        if named or referenced:
            removed.add(payload.get("call_id"))
    if not removed:
        raise ValueError("no consultation tool call found; choose a trial that consulted the skill")
    return [event for event in events if not (
        event.get("payload", {}).get("type") in ("tool_use", "tool_result") and
        event["payload"].get("call_id") in removed)]


def verdicts(summary):
    result = []
    for trial in summary["cases"][0]["trials"]:
        if trial.get("error_message") or trial.get("status") == "error":
            raise ValueError("execution error is not a consultation verdict")
        checks = {item["check_name"]: item for item in trial["check_results"]}
        if any(checks[name].get("not_observable") for name in ("skill_invoked", "max_tool_calls")):
            raise ValueError("unobservable consultation or budget")
        result.append((trial["trial_id"], checks["skill_invoked"]["passed"],
                       checks["max_tool_calls"]["passed"]))
    if not result:
        raise ValueError("no trials")
    return result


def check_flip(present, absent):
    before, after = verdicts(present), verdicts(absent)
    if len(before) != len(after) or not all(
            p[0] == a[0] and p[1] and not a[1] and p[2] == a[2]
            for p, a in zip(before, after)):
        raise ValueError("consultation must flip on every trial; budget verdict must remain unchanged")


def run(run_dir, case_id=None):
    summary = json.loads((run_dir / "summary.json").read_text())
    candidates = [c for c in summary["cases"] if c["id"] == case_id] if case_id else [
        c for c in summary["cases"] if c["id"].startswith("op-")]
    if not candidates:
        raise ValueError("no matching consultation case")
    case = candidates[0]
    if Path(case["id"]).name != case["id"] or case["id"] in (".", ".."):
        raise ValueError("invalid case id")
    project = Path(summary["skill_project_root"]).resolve()
    checks = Path(summary["checks_path"])
    if not checks.is_absolute():
        checks = project / checks
    outputs = []
    with tempfile.TemporaryDirectory(prefix="fastskill-negctl-") as temporary:
        for variant in ("present", "absent"):
            dest = Path(temporary) / variant
            shutil.copytree(run_dir / case["id"], dest / case["id"])
            selected = copy.deepcopy(summary)
            selected.update(cases=[copy.deepcopy(case)], total_cases=1, run_dir=str(dest),
                            checks_path=str(checks), skill_project_root=str(project))
            (dest / "summary.json").write_text(json.dumps(selected))
            if variant == "absent":
                for trace in (dest / case["id"]).glob("trial-*/trace.jsonl"):
                    trial = json.loads((trace.parent / "result.json").read_text())
                    events = [json.loads(line) for line in trace.read_text().splitlines()]
                    kept = remove_consultation(events, trial.get("skill_path"))
                    trace.write_text("\n".join(json.dumps(e) for e in kept) + "\n")
            scored = subprocess.run(["fastskill", "eval", "score", "--run-dir", str(dest),
                                     "--no-fail", "--json"], capture_output=True, text=True, check=True)
            outputs.append(json.loads(scored.stdout))
        check_flip(*outputs)
    print("PASS: consultation flips on every trial; tool-budget verdict unchanged; originals preserved")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("case", nargs="?")
    args = parser.parse_args()
    try:
        run(args.run_dir.resolve(), args.case)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
