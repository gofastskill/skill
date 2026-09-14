"""Validate the shipped authoring project with the candidate CLI, including its ZIP."""
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "fastskill"
CLI = os.environ.get("FASTSKILL_BIN", "fastskill")


def cli(cwd, *args):
    return subprocess.run([CLI, *args], cwd=cwd, capture_output=True, text=True)


class EvalAuthoringTests(unittest.TestCase):
    def assert_valid(self, project, cases):
        result = cli(project, "eval", "validate", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["valid"])
        self.assertEqual(data["case_count"], cases)
        return data

    def test_packaged_example_validates_without_repository_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "fastskill.zip"
            # Matches publish-skill.yml: only fastskill/ contents, at ZIP root.
            with zipfile.ZipFile(archive, "w") as output:
                for path in SKILL.rglob("*"):
                    if path.is_file() and "results" not in path.relative_to(SKILL).parts:
                        output.write(path, path.relative_to(SKILL))
            with zipfile.ZipFile(archive) as packaged:
                packaged.extractall(root / "unpacked")
                self.assertNotIn("evals/v2/patterns.json", packaged.namelist())
                self.assertNotIn("evals/authoring/fixtures/defective-total/ground-truth.md",
                                 packaged.namelist())
            data = self.assert_valid(root / "unpacked/examples/invoice-extraction", 3)
            self.assertEqual(data["judges"], ["extraction-correctness"])
            for document in (root / "unpacked/references").rglob("*.md"):
                for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
                    if "://" not in target and not target.startswith("#"):
                        self.assertTrue((document.parent / target.split("#")[0]).exists(),
                                        f"broken packaged link: {document.name}: {target}")

    def test_contradictory_trigger_is_rejected_and_source_preserved(self):
        source = SKILL / "examples/invoice-extraction"
        original = (source / "evals/checks.toml").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            shutil.copytree(source, project)
            (project / "evals/checks.toml").write_text(
                '[[check]]\nname = "skill_invoked"\nexpected = false\n'
                'cases = ["invoice-basic"]\n')
            result = cli(project, "eval", "validate", "--json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("EVAL_CHECKS_INVALID", result.stdout + result.stderr)
            self.assertIn("invoice-basic", result.stdout + result.stderr)
        self.assertEqual((source / "evals/checks.toml").read_bytes(), original)

    def test_invoice_expected_facts_are_independent_of_target_prompt(self):
        example = SKILL / "examples/invoice-extraction"
        with (example / "evals/prompts.csv").open(newline="") as source:
            cases = list(csv.DictReader(source))
        self.assertEqual([row["should_trigger"] for row in cases], ["true", "true", "false"])
        for row, filename in zip(cases[:2], ["basic.txt", "missing-number.txt"]):
            expected = json.loads(row["expected"])
            fixture = (example / "fixtures" / filename).read_text()
            self.assertIn(expected["currency"], fixture)
            self.assertIn(f'{expected["total"]:.2f}', fixture)
            self.assertNotIn(str(expected["total"]), row["prompt"])
        self.assertIsNone(json.loads(cases[1]["expected"])["invoice_number"])

    def test_existing_suite_fixture_validates_and_keeps_user_note(self):
        source = ROOT / "evals/authoring/fixtures/existing-suite"
        note = (source / "evals/user-note.md").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            shutil.copytree(source, project)
            self.assert_valid(project, 1)
            self.assertEqual((project / "evals/user-note.md").read_bytes(), note)


if __name__ == "__main__":
    unittest.main()
