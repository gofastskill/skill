#!/usr/bin/env python3
"""Validate that current FastSkill guidance uses the canonical command tree."""

from __future__ import annotations

import csv
import json
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

CANONICAL_ENDPOINTS = (
    "skill add",
    "skill remove",
    "skill update",
    "skill list",
    "skill read",
    "skill search",
    "bundle build",
    "bundle add",
    "bundle list",
    "bundle update",
    "bundle remove",
    "bundle override",
    "project init",
    "project install",
    "repo add",
    "repo list",
    "repo info",
    "repo update",
    "repo remove",
    "repo test",
    "repo refresh",
    "repo skills",
    "repo show",
    "repo versions",
    "marketplace create",
    "analysis matrix",
    "analysis cluster",
    "analysis duplicates",
    "eval validate",
    "eval run",
    "eval judge",
    "eval report",
    "eval score",
    "eval scorecard",
    "optimization run",
    "optimization resume",
    "optimization status",
    "optimization inspect",
    "optimization export",
    "index rebuild",
    "cache info",
    "cache clean",
    "server serve",
    "mcp serve",
    "mcp install",
    "mcp list",
    "cli doctor",
    "cli completion",
    "cli spec",
)

RETIRED_INVOCATION = re.compile(
    r"\bfastskill\s+"
    r"(?:init|install|add|remove|update|list|read|search|reindex|serve|doctor|"
    r"completion|spec|repos|analyze|optimize|mcp\s+register)"
    r"(?=\s|[`\"')]|$)"
)

TEXT_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".sh", ".toml", ".txt", ".yml", ".yaml"}
TEXT_ROOTS = (ROOT / ".github", ROOT / "evals", ROOT / "fastskill", ROOT / "specs")
TEXT_FILES = (ROOT / "CLAUDE.md", ROOT / "CONTRIBUTING.md", ROOT / "README.md")


def guidance_files() -> list[Path]:
    files = list(TEXT_FILES)
    for root in TEXT_ROOTS:
        files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES)
    return sorted(files)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)


def main() -> int:
    errors = 0
    corpus_parts: list[str] = []

    for path in guidance_files():
        text = path.read_text(encoding="utf-8")
        corpus_parts.append(text)
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in RETIRED_INVOCATION.finditer(line):
                fail(f"{path.relative_to(ROOT)}:{line_number}: retired invocation {match.group(0)!r}")
                errors += 1

    corpus = "\n".join(corpus_parts)
    missing = [path for path in CANONICAL_ENDPOINTS if f"fastskill {path}" not in corpus]
    for path in missing:
        fail(f"canonical endpoint is not taught anywhere: fastskill {path}")
        errors += 1

    manifest = tomllib.loads((ROOT / "fastskill/skill-project.toml").read_text(encoding="utf-8"))
    manifest_version = manifest["metadata"]["version"]
    skill_text = (ROOT / "fastskill/SKILL.md").read_text(encoding="utf-8")
    skill_version_match = re.search(r"(?m)^version:\s*(\S+)\s*$", skill_text)
    skill_version = skill_version_match.group(1) if skill_version_match else None
    if skill_version != manifest_version:
        fail(f"SKILL.md version {skill_version!r} does not match manifest {manifest_version!r}")
        errors += 1

    patterns = json.loads((ROOT / "evals/v2/patterns.json").read_text(encoding="utf-8"))
    expected_by_id = {case["id"]: case["expected"] for case in patterns["correctness"]}
    with (ROOT / "evals/v2/correctness/prompts.csv").open(newline="", encoding="utf-8") as handle:
        generated_by_id = {row["id"]: row["expected"] for row in csv.DictReader(handle)}
    if generated_by_id != expected_by_id:
        fail("evals/v2/correctness/prompts.csv does not match patterns.json; run evals/v2/build.py")
        errors += 1

    for case_id, expected in expected_by_id.items():
        match = RETIRED_INVOCATION.search(expected)
        if match:
            fail(f"patterns.json {case_id!r} expects retired invocation {match.group(0)!r}")
            errors += 1

    if errors:
        print(f"command namespace validation failed with {errors} error(s)", file=sys.stderr)
        return 1

    print(
        f"command namespace validation passed: {len(CANONICAL_ENDPOINTS)} canonical endpoints, "
        f"{len(expected_by_id)} correctness references"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
