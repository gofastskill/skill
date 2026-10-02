"""Test the acceptance harness with deterministic edits, not live-agent claims."""
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
spec = importlib.util.spec_from_file_location("workflow", ROOT / "evals/authoring/workflow.py")
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class WorkflowTests(unittest.TestCase):
    def test_cli_prepare_verify_and_error(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory) / "task"
            with patch("sys.argv", ["workflow.py", "prepare", "repair", str(root)]):
                workflow.main()
            (root / "target/evals/checks.toml").write_text("")
            with patch("sys.argv", ["workflow.py", "verify", str(root)]):
                workflow.main()
            with patch("sys.argv", ["workflow.py", "prepare", "repair", str(root)]), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                workflow.main()
            self.assertEqual(caught.exception.code, 1)

    def test_missing_notes_and_negative_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "task"
            workflow.prepare("extend", root)
            prompts = root / "target/evals/prompts.csv"
            original = prompts.read_text()
            prompts.write_text(original + "extra,Another release request,true,positive\n")
            with self.assertRaisesRegex(ValueError, "negative-trigger"):
                workflow.verify(root)
            prompts.write_text(original + "negative,Explain Python lists,false,negative\n")
            with self.assertRaisesRegex(ValueError, "review notes"):
                workflow.verify(root)

    def test_preparation_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                workflow.prepare("extend", Path(directory))
            root = Path(directory)
            link = root / "dangling"
            link.symlink_to(root / "must-not-be-created", target_is_directory=True)
            with patch("sys.argv", ["workflow.py", "prepare", "extend", str(link)]), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                workflow.main()
            self.assertFalse((root / "must-not-be-created").exists())
            self.assertTrue(link.is_symlink())

    def test_create_repair_extend_and_preservation_failures(self):
        for scenario in workflow.SCENARIOS:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "task"
                workflow.prepare(scenario, root)
                target = root / "target"
                with self.assertRaises((ValueError, FileNotFoundError)):
                    workflow.verify(root)
                if scenario == "create":
                    example = ROOT / "fastskill/examples/invoice-extraction"
                    shutil.copytree(example / "evals", target / "evals")
                    shutil.copy2(example / "skill-project.toml", target / "skill-project.toml")
                elif scenario == "repair":
                    (target / "evals/checks.toml").write_text("")
                else:
                    prompts = target / "evals/prompts.csv"
                    prompts.write_text(prompts.read_text() + "negative,Explain Python lists,false,negative\n")
                (target / "evals/review-notes.md").write_text("Deterministic harness fixture; not a live authoring run.")
                result = workflow.verify(root)
                self.assertEqual(result["preservation"], "passed")
                self.assertEqual(result["target_pilot"], "not run")
                skill = target / "SKILL.md"
                original = skill.read_bytes()
                skill.write_text("unintended change")
                with self.assertRaisesRegex(ValueError, "protected file"):
                    workflow.verify(root)
                skill.write_bytes(original)
                if scenario != "create":
                    prompts = target / "evals/prompts.csv"
                    prompts.write_text(prompts.read_text().replace("invoice-basic" if scenario == "repair" else "release-basic", "changed-id"))
                    with self.assertRaises(ValueError):
                        workflow.verify(root)


if __name__ == "__main__":
    unittest.main()
