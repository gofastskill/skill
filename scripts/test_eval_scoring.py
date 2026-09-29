"""Exercise real scorer verdicts; synthetic traces are not model-run evidence."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
CLI = os.environ.get("FASTSKILL_BIN", "fastskill")


def score_fixture(source, destination, case_id=None, answer=None, tool_output=None):
    shutil.copytree(source, destination)
    summary = json.loads((destination / "summary.json").read_text())
    old_id = summary["cases"][0]["id"]
    if case_id:
        (destination / old_id).rename(destination / case_id)
        summary["cases"][0].update(id=case_id, should_trigger=True)
        summary["checks_path"] = str(ROOT / "evals/v2/correctness/checks.toml")
    else:
        summary["checks_path"] = str(ROOT / "evals/checks.toml")
    summary.update(run_dir=str(destination), skill_project_root=str(ROOT))
    (destination / "summary.json").write_text(json.dumps(summary))
    if answer is not None:
        path = destination / (case_id or old_id) / "trial-1/trace.jsonl"
        events = [json.loads(line) for line in path.read_text().splitlines()]
        events[-1]["payload"]["text"] = answer
        if tool_output is not None:
            events[2]["payload"]["output"] = tool_output
        path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    result = subprocess.run([CLI, "eval", "score", "--run-dir", str(destination), "--json"],
                            cwd=ROOT, capture_output=True, text=True)
    return result, json.loads(result.stdout)


class ScoringTests(unittest.TestCase):
    def test_fixtures_fail_only_for_intended_check(self):
        for fixture, expected in (("pass", True), ("fail", False)):
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as directory:
                result, data = score_fixture(ROOT / "evals/fixtures" / fixture,
                                             Path(directory) / "run")
                self.assertEqual(result.returncode, 0 if expected else 2, result.stderr)
                self.assertEqual(data["suite_pass"], expected)
                self.assertEqual(len(data["cases"]), 1)
                trial = data["cases"][0]["trials"][0]
                self.assertIsNone(trial.get("error_message"))
                checks = {c["check_name"]: c for c in trial["check_results"]}
                self.assertEqual(checks["skill_invoked"]["passed"], expected)
                self.assertTrue(checks["max_tool_calls"]["passed"])
                self.assertFalse(any(c.get("not_observable") for c in checks.values()))

    def test_correct_refusal_is_not_rejected_by_literal_mention(self):
        with tempfile.TemporaryDirectory() as directory:
            result, data = score_fixture(ROOT / "evals/fixtures/pass", Path(directory) / "run",
                "c-no-publish", "There is no fastskill publish command. Use Git or a ZIP URL instead.")
            self.assertEqual(result.returncode, 0, result.stderr)
            checks = data["cases"][0]["trials"][0]["check_results"]
            self.assertNotIn("trigger_expectation", [c["check_name"] for c in checks])
            # No semantic verdict is inferred: this case needs the optional judge.

    def test_trace_fragment_limitations_remain_explicit(self):
        examples = [
            ("c-tag-pin", "fastskill skill remove widgets --tag v2.1.0", None),
            ("c-serve-port", "fastskill server serve --port 9123", None),
            ("c-tag-pin", "I do not know.", "--tag v2.1.0"),
        ]
        for case, answer, output in examples:
            with self.subTest(answer=answer), tempfile.TemporaryDirectory() as directory:
                result, data = score_fixture(ROOT / "evals/fixtures/pass", Path(directory) / "run",
                                             case, answer, output)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(data["suite_pass"])
        # These false semantic positives must never be relabelled answer accuracy.
        import tomllib
        metrics = tomllib.loads((ROOT / "evals/v2/metrics.toml").read_text())
        metric = next(m for m in metrics["metric"] if "command_contains" in m.get("checks", []))
        self.assertIn("not semantic accuracy", metric["name"])
        self.assertNotIn("c-no-publish", metric["cases"])

    def test_missing_fixture_is_not_a_quality_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([CLI, "eval", "score", "--run-dir", directory, "--json"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertFalse(data["success"])
            self.assertIn("error", data)
            self.assertNotIn("cases", data)


if __name__ == "__main__":
    unittest.main()
