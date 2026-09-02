#!/usr/bin/env python3
"""Fail the build if any eval pattern is an oracle that cannot fail.

Spec 001 C4: `trigger_expectation` / `command_contains` substring-match against the whole
trace, and the trace contains the full text of every file the agent read. The skill payload
is exactly what an agent reads when it consults the skill, so a pattern occurring anywhere
in that payload matches whether or not the agent answered correctly.

This guard proves, mechanically, that no pattern in patterns.json occurs in the shipped
skill payload. Run it before every sweep. A green guard is what makes the numbers mean
something.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
SKILL_DIR = REPO / "fastskill"

def payload_files():
    """Every file an agent could read when it opens the skill."""
    return sorted(p for p in SKILL_DIR.rglob("*") if p.is_file())

def main():
    patterns = json.loads((HERE / "patterns.json").read_text())

    corpus = {}
    for p in payload_files():
        try:
            corpus[p.relative_to(REPO)] = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    if not corpus:
        print(f"FAIL: no skill payload found under {SKILL_DIR} — guard cannot prove anything")
        return 1

    checked = []
    checked.append(("consultation_pattern", patterns["consultation_pattern"]))
    for case in patterns["correctness"]:
        for pat in case.get("require", []):
            checked.append((f"{case['id']}.require", pat))
        for pat in case.get("forbid", []):
            checked.append((f"{case['id']}.forbid", pat))

    violations = []
    for owner, pat in checked:
        for relpath, text in corpus.items():
            if pat in text:
                violations.append((owner, pat, relpath))

    width = max(len(o) for o, _ in checked)
    for owner, pat in checked:
        bad = [v for v in violations if v[0] == owner and v[1] == pat]
        status = "VACUOUS" if bad else "ok"
        print(f"  {owner:<{width}}  {status:<8} {pat!r}")

    print()
    print(f"scanned {len(corpus)} skill payload file(s), {len(checked)} pattern(s)")
    if violations:
        print()
        print("FAIL: these patterns occur in the skill payload and would match on a mere read:")
        for owner, pat, relpath in violations:
            print(f"  {owner}: {pat!r} occurs in {relpath}")
        return 1
    print("PASS: no pattern occurs in the skill payload — every oracle can fail")
    return 0

if __name__ == "__main__":
    sys.exit(main())
