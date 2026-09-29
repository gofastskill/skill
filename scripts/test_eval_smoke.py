"""No model calls: real validation plus a recording runtime stub."""
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from scripts.test_eval_scripts import shell

ROOT = Path(__file__).resolve().parent.parent


class SmokeTests(unittest.TestCase):
    def test_six_cases_validate_without_a_judge(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "project"
            subprocess.run(["bash", str(ROOT / "evals/v2/stage.sh"), "smoke", str(dest), "1"], check=True)
            result = subprocess.run([os.environ.get("FASTSKILL_BIN", "fastskill"), "eval", "validate", "--json"],
                                    cwd=dest / "fastskill", capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            self.assertEqual(data["case_count"], 6)
            self.assertEqual(data["judges"], [])
            self.assertEqual(data["trials_per_case"], 1)
            with (dest / "evals/prompts.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(sum(row["should_trigger"] == "false" for row in rows), 2)

    def test_runner_forwards_model_and_failure_and_refuses_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stub = root / "fastskill"
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'
                            'if [ "$2" = run ]; then exit 7; fi\n')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       CALL_LOG=str(root / "calls"))
            command = shell(ROOT / "evals/smoke.sh", "claude", str(root / "out"), "test-model")
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            calls = (root / "calls").read_text()
            self.assertIn("--model test-model", calls)
            self.assertNotIn("--judge", calls)
            self.assertNotIn("--no-fail", calls)
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / "calls").read_text(), calls)


if __name__ == "__main__":
    unittest.main()
