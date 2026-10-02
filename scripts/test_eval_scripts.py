"""Exercise preservation and runner-error behavior without model calls."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "evals/v2/stage.sh"


def shell(script, *args):
    coverage = os.environ.get("KCOV")
    if coverage:
        output = tempfile.mkdtemp(prefix="shell-", dir=os.environ["KCOV_OUTPUT"])
        return [coverage, "--bash-method=DEBUG", "--configure=bash-use-basic-parser=1",
                "--exclude-region=import sys:PY",
                "--include-pattern=/evals/", output, str(script), *args]
    return ["bash", str(script), *args]


class EvalScriptsTests(unittest.TestCase):
    def test_staging_preserves_existing_directory_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "existing"
            existing.mkdir()
            note = existing / "user-note"
            note.write_text("keep this")
            link = root / "link"
            link.symlink_to(existing, target_is_directory=True)
            for dest in (existing, link):
                result = subprocess.run(shell(STAGE, "consultation", str(dest)),
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already exists", result.stderr)
                self.assertEqual(note.read_text(), "keep this")
            self.assertTrue(link.is_symlink())

    def test_staged_project_keeps_payload_and_judge_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "fresh"
            subprocess.run(shell(STAGE, "correctness", str(dest), "1"), check=True)
            self.assertEqual((dest / "fastskill/SKILL.md").read_bytes(),
                             (ROOT / "fastskill/SKILL.md").read_bytes())
            self.assertTrue((dest / "evals/judge-prompt.md").is_file())
            self.assertTrue((dest / "fastskill/references/eval-authoring.md").is_file())

    def test_subset_runner_failure_is_nonzero_and_preserves_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "fastskill"
            executable.write_text("#!/bin/sh\necho deliberate-runtime-failure >&2\nexit 23\n")
            executable.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"])
            # kcov 38 suppresses output for this unconditional failing child.
            # Exercise this assertion directly; the full-sweep test instruments
            # the same runner error path with the controllable stub below.
            result = subprocess.run(["bash", str(ROOT / "evals/v2/run.sh"), "claude",
                                     str(root / "out"), "1", "consultation"],
                                    env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("RUNNER ERROR", result.stdout, result.stderr)
            self.assertIn("deliberate-runtime-failure",
                          (root / "out/consultation.log").read_text())

    def test_unknown_suite_and_missing_judge_credentials_fail_before_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(shell(STAGE, "../", str(root / "stage")),
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "stage").exists())
            env = {k: v for k, v in os.environ.items() if k not in ("AIKIT_LLM_URL", "JUDGE_API_KEY")}
            for suites, expected in [(["unknown"], "no such suite"), (["correctness"], "endpoint")]:
                result = subprocess.run(shell(ROOT / "evals/v2/run.sh", "claude",
                                               str(root / "out"), "1", *suites),
                                        env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stdout + result.stderr)

    def test_sweeps_preserve_stages_and_propagate_runner_and_scorecard_verdicts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "fastskill"
            executable.write_text(
                '#!/bin/sh\n'
                'if [ "$2" = scorecard ]; then exit "${SCORE_EXIT:-0}"; fi\n'
                'while [ "$#" -gt 0 ]; do\n'
                '  if [ "$1" = --output-dir ]; then shift; mkdir -p "$1"; fi\n'
                '  shift\n'
                'done\n'
                'echo "1/1 passed"\nexit "${RUN_EXIT:-0}"\n')
            executable.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       AIKIT_LLM_URL="http://unused.invalid/v1", JUDGE_API_KEY="test-only",
                       JUDGE_MODEL="test-only", TARGET_MODEL="test-target")
            for index, (suites, run_exit, score_exit) in enumerate([
                    (["consultation"], "0", "0"), ([], "0", "0"),
                    ([], "23", "0"), ([], "0", "9")]):
                out = root / f"out-{index}"
                result = subprocess.run(shell(ROOT / "evals/v2/run.sh", "claude", str(out),
                                               "1", *suites), capture_output=True, text=True,
                                        env=dict(env, RUN_EXIT=run_exit, SCORE_EXIT=score_exit))
                self.assertEqual(result.returncode == 0, run_exit == score_exit == "0",
                                 result.stdout + result.stderr)
                self.assertTrue(list(out.glob(".stage-*/consultation/fastskill/SKILL.md")))


if __name__ == "__main__":
    unittest.main()
