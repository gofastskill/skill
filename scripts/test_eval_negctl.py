"""Controlled trace mutation, including independent per-trial skill paths."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("negctl", ROOT / "evals/v2/negctl.py")
negctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(negctl)


class NegativeControlTests(unittest.TestCase):
    def test_cli_reports_missing_run_as_error(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("sys.argv", ["negctl.py", directory]), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            negctl.main()
        self.assertEqual(caught.exception.code, 1)

    def test_real_scorer_with_two_distinct_trial_paths_preserves_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            shutil.copytree(ROOT / "evals/fixtures/pass", run)
            (run / "eval-skill").rename(run / "op-example")
            summary = json.loads((run / "summary.json").read_text())
            case = summary["cases"][0]
            case.update(id="op-example", should_trigger=True, total_trials=2)
            case["trials"].append(dict(case["trials"][0], trial_id=2))
            summary.update(checks_path=str(ROOT / "evals/v2/consultation/checks.toml"),
                           skill_project_root=str(ROOT), trials_per_case=2, model="preserved-model")
            (run / "summary.json").write_text(json.dumps(summary))
            shutil.copytree(run / "op-example/trial-1", run / "op-example/trial-2")
            for number in (1, 2):
                trial = run / f"op-example/trial-{number}"
                path = f"/tmp/independent-{number}/SKILL.md"
                result = json.loads((trial / "result.json").read_text())
                result.update(trial_id=number, skill_path=path)
                (trial / "result.json").write_text(json.dumps(result))
                events = [json.loads(line) for line in (trial / "trace.jsonl").read_text().splitlines()]
                events[1]["payload"].update(tool_name="Read", input={"file_path": path})
                (trial / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
            originals = {p: p.read_bytes() for p in run.rglob("*") if p.is_file()}
            with patch("sys.argv", ["negctl.py", str(run)]):
                negctl.main()
            self.assertTrue(all(p.read_bytes() == data for p, data in originals.items()))
            with self.assertRaisesRegex(ValueError, "no matching"):
                negctl.run(run, "unknown")

    def test_removes_only_consultation_calls_not_answer_mentions(self):
        events = [
            {"payload": {"type": "tool_use", "call_id": "read", "tool_name": "Skill", "input": {"skill": "fastskill"}}},
            {"payload": {"type": "tool_result", "call_id": "read", "output": "content"}},
            {"payload": {"type": "message", "text": "/tmp/skill/SKILL.md"}},
        ]
        self.assertEqual(negctl.remove_consultation(events, None), events[2:])
        with self.assertRaises(ValueError):
            negctl.remove_consultation(events[2:], "/tmp/skill/SKILL.md")

    def test_requires_check_specific_flip_and_unchanged_budget(self):
        def summary(invoked, budget=True, **extra):
            return {"cases": [{"trials": [dict(trial_id=1, check_results=[
                {"check_name": "skill_invoked", "passed": invoked},
                {"check_name": "max_tool_calls", "passed": budget}], **extra)]}]}
        negctl.check_flip(summary(True), summary(False))
        for absent in (summary(True), summary(False, False), summary(False, status="error")):
            with self.assertRaises(ValueError):
                negctl.check_flip(summary(True), absent)
        data = summary(False)
        data["cases"][0]["trials"][0]["check_results"][0]["not_observable"] = True
        with self.assertRaises(ValueError):
            negctl.verdicts(data)
        with self.assertRaises(ValueError):
            negctl.verdicts({"cases": [{"trials": []}]})


if __name__ == "__main__":
    unittest.main()
