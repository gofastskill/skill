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
    """cases: [(case_id, [ {checks: {name: bool}, tools: int, usds: [float]} ])]"""
    d = pathlib.Path(root, suite, "2026-01-01T00-00-00Z", "pi")
    out = []
    for cid, trials in cases:
        for i, tr in enumerate(trials, 1):
            td = d / cid / f"trial-{i}"
            td.mkdir(parents=True)
            lines = ["not json at all"]
            for u in tr["usds"]:
                lines += [noise(u), turn(u), noise(u)]
            (td / "stdout.txt").write_text("\n".join(lines) + "\n")
            # A dead trial has only the system retry chatter and no assistant text.
            msgs = [json.dumps({"seq": 1, "payload": {"type": "message",
                                                      "role": "system",
                                                      "text": "pi auto_retry_end"}})]
            if tr.get("alive", True):
                msgs.append(json.dumps({"seq": 2, "payload": {"type": "message",
                                                              "text": "here is my answer"}}))
            (td / "trace.jsonl").write_text("\n".join(msgs) + "\n")
        jt = []
        for i, tr in enumerate(trials, 1):
            ok = all(tr["checks"].values())
            jt.append({
                "trial_id": i, "status": "passed" if ok else "failed",
                "command_count": tr["tools"], "input_tokens": None, "output_tokens": None,
                "check_results": [{"check_name": k, "passed": v, "required": True,
                                   "message": None} for k, v in tr["checks"].items()],
                "error_message": None,
            })
        n_ok = sum(1 for t in jt if t["status"] == "passed")
        out.append({"id": cid, "status": "passed" if n_ok == len(jt) else "failed",
                    "command_count": sum(t["command_count"] for t in jt),
                    "pass_count": n_ok, "total_trials": len(jt),
                    "pass_rate": n_ok / len(jt), "trials": jt})
    (d / "summary.json").write_text(json.dumps({"cases": out}))


def T(trigger=True, budget=None, tools=0, usds=(), assertion="trigger_expectation",
      alive=True):
    c = {assertion: trigger}
    if budget is not None:
        c["max_tool_calls"] = budget
    return {"checks": c, "tools": tools, "usds": list(usds), "alive": alive}


def main():
    root = tempfile.mkdtemp()
    try:
        # consultation, 2 cases x 4 trials, TWO required checks each.
        # trigger: op-a 4/4, op-b 2/4            -> 6/8  = 0.75
        # budget:  op-a 4/4, op-b 3/4            -> 7/8  = 0.875
        # A trial that busts the budget but DID open the skill must not lower the
        # skill-open rate. op-b trial-4 is exactly that case.
        write_suite(root, "consultation", [
            ("op-a", [T(True, True, 2, [0.01]) for _ in range(4)]),
            ("op-b", [T(True, True, 40, [0.02, 0.03]),
                      T(False, True, 40, [0.02]),
                      T(False, True, 40, [0.02]),
                      T(True, False, 40, [0.02])]),
        ])
        # restraint: 1 case x 4 trials, 3 pass => 3/4
        write_suite(root, "restraint", [
            ("off-x", [T(True, None, 0), T(True, None, 0), T(True, None, 0), T(False, None, 0)]),
            # An outage: 4 trials with no model output. A negative oracle passes
            # vacuously on an empty trace, so counting these would report an outage
            # as perfect restraint.
            ("off-dead", [T(True, None, 0, alive=False) for _ in range(4)]),
        ])
        # correctness: two SEPARATE single-case suites, must fold into one family.
        # c1 asserts a required flag (command_contains), c2 forbids a command
        # (negative trigger_expectation). Both are answer-accuracy evidence and both
        # must land in the same metric -- an earlier version counted only c2.
        write_suite(root, "correctness-c1",
                    [("c1", [T(True, True, 3, assertion="command_contains") for _ in range(4)])])
        write_suite(root, "correctness-c2",
                    [("c2", [T(False, True, 3) for _ in range(4)])])

        checks, tools, usd, rows, dead = aggregate.collect(root)
        fails = []

        def check(name, got, want):
            ok = abs(got - want) <= 1e-9 if isinstance(want, float) else got == want
            print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
            if not ok:
                fails.append(name)

        def rate(f, c):
            a = checks[(f, c)]
            return a["pass"] / a["total"]

        check("skill-open rate is trigger only", rate("consultation", "trigger_expectation"), 0.75)
        check("tool-budget rate is separate", rate("consultation", "max_tool_calls"), 0.875)
        check("restraint rate", rate("restraint", "trigger_expectation"), 0.75)
        acc = aggregate.metric(checks, "correctness",
                               {"command_contains", "trigger_expectation"})
        check("accuracy folds both assertion shapes", acc[1], 8)
        check("accuracy rate", acc[0] / acc[1], 0.5)
        check("accuracy case count", acc[2], 2)
        check("command_contains alone is not the metric",
              checks[("correctness", "command_contains")]["total"], 4)

        # Every observed assertion check must be claimed by some metric.
        check("no orphan checks in this sweep", aggregate.orphans(checks), [])
        checks[("correctness", "some_new_check")] = {"pass": 1, "total": 1, "cases": {"cX"}}
        check("orphan guard fires on an unclaimed check",
              aggregate.orphans(checks), [("correctness", "some_new_check")])
        del checks[("correctness", "some_new_check")]

        check("tools from consultation only", sorted(tools), [2, 2, 2, 2, 40, 40, 40, 40])
        check("p95 tool calls", aggregate.p95(tools), 40)

        # cost: 4*0.01 + (0.02+0.03) + 3*0.02 = 0.15. Each turn_end is flanked by two
        # streamed snapshots with the same value; counting those would give 0.45.
        check("cost counts turn_end only", round(usd, 10), 0.15)

        by_id = {r["id"]: r for r in rows}
        check("dead trials detected", len(dead), 4)
        check("dead trials all from off-dead", {d[1] for d in dead}, {"off-dead"})
        check("dead trials excluded from restraint rate",
              rate("restraint", "trigger_expectation"), 0.75)
        check("row count", len(rows), 6)
        check("dead count carried on the row", by_id["off-dead"]["dead"], 4)
        check("mean tools per trial, not the sum", by_id["op-b"]["mean_tools"], 40.0)
        check("failure attributed to the right check",
              by_id["op-b"]["fail_by"], {"trigger_expectation": 2, "max_tool_calls": 1})
        check("clean case has no attribution", by_id["op-a"]["fail_by"], {})

        # Negative control: the aggregator must be able to fail.
        p = next(pathlib.Path(root).glob("consultation/*/pi/summary.json"))
        d = json.loads(p.read_text())
        d["cases"][0]["trials"][0]["check_results"][0]["passed"] = False
        p.write_text(json.dumps(d))
        checks2, _, _, _, _ = aggregate.collect(root)
        r2 = checks2[("consultation", "trigger_expectation")]["pass"] / 8
        check("rate responds to a flipped check", abs(r2 - 0.625) <= 1e-9, True)

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
