#!/usr/bin/env python3
"""Prepare and verify small authoring tasks for the user's chosen agent.

No model invocation or fabricated live-run verdicts. A prepared task stays pending
until an agent edits target/ and the real validator and preservation checks pass.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ("create", "repair", "extend")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def prepare(scenario, destination):
    destination.mkdir()  # Refuse an existing destination, including a symlink.
    source = ROOT / "evals/authoring/fixtures" / (
        "invoice-no-evals" if scenario == "create" else "existing-suite")
    if scenario == "repair":
        source = ROOT / "fastskill/examples/invoice-extraction"
    target = destination / "target"
    shutil.copytree(source, target)
    if scenario == "repair":
        (target / "evals/checks.toml").write_text(
            '[[check]]\nname = "skill_invoked"\nexpected = false\n'
            'cases = ["invoice-basic"]\nrequired = true\n')
    protected = {}
    for path in target.rglob("*"):
        if path.is_file() and path.relative_to(target).parts[0] != "evals":
            protected[str(path.relative_to(target))] = digest(path)
    if scenario == "extend":
        for name in ("checks.toml", "user-note.md"):
            path = target / "evals" / name
            protected[str(path.relative_to(target))] = digest(path)
    state = {"scenario": scenario, "protected": protected,
             "original_rows": rows(target / "evals/prompts.csv") if scenario != "create" else []}
    (destination / "baseline.json").write_text(json.dumps(state, indent=2))
    shutil.copytree(ROOT / "fastskill", destination / "authoring-skill")
    instructions = {
        "create": "Create a small valid invoice-extraction suite with at least one positive and one unrelated negative case. Expected outcomes must derive from the fixtures, not be included as answers in the task prompts.",
        "repair": "Diagnose and repair the invalid eval configuration without changing any prompt rows, target instructions, manifest or fixtures.",
        "extend": "Add an unrelated negative-trigger case while preserving every existing row, check, fixture and user note.",
    }
    (destination / "task.md").write_text(
        "Read authoring-skill/SKILL.md and its eval-authoring reference. Work only in target/. "
        + instructions[scenario] + " Write target/evals/review-notes.md explaining the change and remaining limitations. "
        "Run fastskill eval validate from target/. Do not run target agents or judges; "
        "authoring only is authorized. Do not edit baseline.json or authoring-skill/.\n")
    return destination / "task.md"


def verify(destination, cli="fastskill"):
    state = json.loads((destination / "baseline.json").read_text())
    target = destination / "target"
    for relative, expected in state["protected"].items():
        path = target / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"protected file changed: {relative}")
    result = subprocess.run([cli, "eval", "validate", "--json"], cwd=target,
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError("validation failed: " + result.stdout + result.stderr)
    validation = json.loads(result.stdout)
    if not validation.get("valid"):
        raise ValueError("validator did not confirm validity")
    current = rows(target / "evals/prompts.csv")
    original = state["original_rows"]
    scenario = state["scenario"]
    if scenario == "repair" and current != original:
        raise ValueError("repair changed prompt rows")
    if scenario == "extend" and (len(current) <= len(original) or current[:len(original)] != original):
        raise ValueError("extension must preserve original rows and add a case")
    relevant = current[len(original):] if scenario == "extend" else current
    if scenario != "repair" and not any(r.get("should_trigger", "").lower() in ("false", "0") for r in relevant):
        raise ValueError("missing explicit negative-trigger case")
    if scenario == "create" and not any(r.get("should_trigger", "").lower() in ("true", "1") for r in current):
        raise ValueError("missing positive-trigger case")
    notes = target / "evals/review-notes.md"
    if not notes.is_file() or not notes.read_text().strip():
        raise ValueError("missing review notes")
    return {"scenario": scenario, "validated_cases": len(current), "preservation": "passed",
            "semantic_quality": "requires human review", "target_pilot": "not run"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    setup = commands.add_parser("prepare")
    setup.add_argument("scenario", choices=SCENARIOS)
    setup.add_argument("destination", type=Path)
    check = commands.add_parser("verify")
    check.add_argument("destination", type=Path)
    check.add_argument("--cli", default="fastskill")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            # Do not follow a dangling destination symlink before mkdir refuses it.
            print(prepare(args.scenario, args.destination.absolute()))
        else:
            print(json.dumps(verify(args.destination.resolve(), args.cli), indent=2))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
