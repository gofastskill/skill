#!/usr/bin/env python3
"""Tests for the deterministic command namespace validator."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("check-command-namespaces.py")
SPEC = importlib.util.spec_from_file_location("check_command_namespaces", SCRIPT)
assert SPEC and SPEC.loader
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class CommandNamespaceCheckTests(unittest.TestCase):
    def make_repository(
        self,
        root: Path,
        *,
        skill_text: str,
        manifest_version: str = "2.0.0",
        expected: str = "fastskill skill add ./widget",
        generated_expected: str | None = None,
    ) -> None:
        for directory in (".github", "evals/v2/correctness", "fastskill", "specs"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        for filename in ("CLAUDE.md", "CONTRIBUTING.md", "README.md"):
            (root / filename).write_text("", encoding="utf-8")
        (root / "fastskill/SKILL.md").write_text(skill_text, encoding="utf-8")
        (root / "fastskill/skill-project.toml").write_text(
            f'[metadata]\nversion = "{manifest_version}"\n', encoding="utf-8"
        )
        patterns = {"correctness": [{"id": "case-1", "expected": expected}]}
        (root / "evals/v2/patterns.json").write_text(json.dumps(patterns), encoding="utf-8")
        csv_expected = generated_expected if generated_expected is not None else expected
        (root / "evals/v2/correctness/prompts.csv").write_text(
            f"id,expected\ncase-1,{csv_expected}\n", encoding="utf-8"
        )

    @contextlib.contextmanager
    def repository_context(self, root: Path, endpoints: tuple[str, ...]):
        roots = tuple(root / path for path in (".github", "evals", "fastskill", "specs"))
        files = tuple(root / path for path in ("CLAUDE.md", "CONTRIBUTING.md", "README.md"))
        with (
            mock.patch.object(CHECK, "ROOT", root),
            mock.patch.object(CHECK, "TEXT_ROOTS", roots),
            mock.patch.object(CHECK, "TEXT_FILES", files),
            mock.patch.object(CHECK, "CANONICAL_ENDPOINTS", endpoints),
        ):
            yield

    def test_accepts_canonical_guidance_and_matching_generated_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(
                root,
                skill_text="---\nversion: 2.0.0\n---\nfastskill skill add ./widget\n",
            )
            with self.repository_context(root, ("skill add",)):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(CHECK.main(), 0)
                self.assertIn("1 canonical endpoints", stdout.getvalue())

    def test_reports_each_contract_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(
                root,
                skill_text="fastskill add ./widget\n",
                manifest_version="2.0.0",
                expected="fastskill add ./widget",
                generated_expected="fastskill skill add ./different-widget",
            )
            with self.repository_context(root, ("skill add", "bundle add")):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(CHECK.main(), 1)
                output = stderr.getvalue()
                self.assertIn("retired invocation", output)
                self.assertIn("canonical endpoint is not taught", output)
                self.assertIn("does not match manifest", output)
                self.assertIn("does not match patterns.json", output)
                self.assertIn("expects retired invocation", output)

    def test_rejects_removed_mcp_register_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(
                root,
                skill_text=(
                    "---\nversion: 2.0.0\n---\n"
                    "fastskill skill add ./widget\n"
                    "fastskill mcp register --agent claude --scope project\n"
                ),
            )
            with self.repository_context(root, ("skill add",)):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(CHECK.main(), 1)
                self.assertIn(
                    "retired invocation 'fastskill mcp register'",
                    stderr.getvalue(),
                )


if __name__ == "__main__":
    unittest.main()
