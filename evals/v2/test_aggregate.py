#!/usr/bin/env python3
"""Self-test for aggregate.py against a synthetic sweep with hand-computed answers.

The aggregator produces the numbers the spec reports. If it is wrong, the whole
measurement is wrong, so it gets its own oracle. Run: python3 evals/v2/test_aggregate.py
"""
import json
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import aggregate  # noqa: E402


def turn(usd):
    return json.dumps({"type": "turn_end", "parts": [{"cost": {"total": usd}}]})


def noise(usd):
    """A streamed snapshot carrying the same cumulative cost. Must NOT be counted."""
    return json.dumps({"type": "message_update", "parts": [{"cost": {"total": usd}}]})


def write_suite(root, suite, cases):
    """cases: [(case_id, [(passed: bool, tool_calls: int, [turn_usd, ...])])]"""
    d = pathlib.Path(root, suite, "2026-01-01T00-00-00Z", "pi")
    out = []
    for cid, trials in cases:
        for i, (ok, tc, usds) in enumerate(trials, 1):
            td = d / cid / f"trial-{i}"
            td.mkdir(parents=True)
            lines = ["not json at all"]
            for u in usds:
                lines += [noise(u), turn(u), noise(u)]
            (td / "stdout.txt").write_text("\n".join(lines) + "\n")
        out.append({
            "id": cid,
            "status": "passed" if all(t[0] for t in trials) else "failed",
            "command_count": trials[0][1],
            "pass_count": sum(1 for t in trials if t[0]),
            "total_trials": len(trials),
            "pass_rate": sum(1 for t in trials if t[0]) / len(trials),
            "trials": [{"trial_id": i,
                        "status": "passed" if ok else "failed",
                        "command_count": tc,
                        "input_tokens": None, "output_tokens": None,
                        "check_results": [], "error_message": None}
                       for i, (ok, tc, _) in enumerate(trials, 1)],
        })
    (d / "summary.json").write_text(json.dumps({"cases": out}))


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol


def main():
    root = tempfile.mkdtemp()
    try:
        # consultation: 2 cases x 4 trials. c-a passes 4/4, c-b passes 1/4 => 5/8 = 0.625
        write_suite(root, "consultation", [
            ("op-a", [(True, 2, [0.01]), (True, 2, [0.01]), (True, 2, [0.01]), (True, 2, [0.01])]),
            ("op-b", [(True, 40, [0.02, 0.03]), (False, 40, [0.02]), (False, 40, [0.02]), (False, 40, [0.02])]),
        ])
        # restraint: 1 case x 4 trials, 3 pass => 3/4 = 0.75
        write_suite(root, "restraint", [
            ("off-x", [(True, 0, []), (True, 0, []), (True, 0, []), (False, 0, [])]),
        ])
        # correctness: two SEPARATE single-case suites, must fold into one family.
        # 4/4 + 0/4 => 4/8 = 0.5
        write_suite(root, "correctness-c1", [("c1", [(True, 3, [])] * 4)])
        write_suite(root, "correctness-c2", [("c2", [(False, 3, [])] * 4)])

        fam, tools, usd, rows = aggregate.collect(root)

        fails = []

        def check(name, got, want):
            ok = approx(got, want) if isinstance(want, float) else got == want
            print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
            if not ok:
                fails.append(name)

        check("consultation rate", fam["consultation"]["pass"] / fam["consultation"]["total"], 0.625)
        check("restraint rate", fam["restraint"]["pass"] / fam["restraint"]["total"], 0.75)
        check("correctness folds 2 suites into 1 family", fam["correctness"]["total"], 8)
        check("correctness rate", fam["correctness"]["pass"] / fam["correctness"]["total"], 0.5)
        check("correctness case count", fam["correctness"]["cases"], 2)

        # tool calls: consultation only -> [2,2,2,2, 40,40,40,40]
        check("tools collected from consultation only", sorted(tools), [2, 2, 2, 2, 40, 40, 40, 40])
        check("p95 tool calls", aggregate.p95(tools), 40)

        # cost: 4*0.01 + (0.02+0.03) + 3*0.02 = 0.04 + 0.05 + 0.06 = 0.15
        # Each turn_end is flanked by two message_update snapshots carrying the same
        # value; counting those would give 3x. This assertion is what catches that.
        check("cost counts turn_end only", round(usd, 10), 0.15)

        check("row count", len(rows), 5)

        # Negative control: the aggregator must be able to fail. Corrupt one trial's
        # status and confirm the consultation rate moves.
        p = next(pathlib.Path(root).glob("consultation/*/pi/summary.json"))
        d = json.loads(p.read_text())
        d["cases"][0]["trials"][0]["status"] = "failed"
        p.write_text(json.dumps(d))
        fam2, _, _, _ = aggregate.collect(root)
        r2 = fam2["consultation"]["pass"] / fam2["consultation"]["total"]
        check("rate responds to a flipped trial", approx(r2, 0.5), True)

        print()
        if fails:
            print(f"FAILED: {len(fails)} assertion(s): {', '.join(fails)}")
            return 1
        print("PASS: aggregate.py matches hand-computed expectations")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
