#!/usr/bin/env python3
"""Aggregate a spec-001 sweep into the four metrics of §6.

Rates are computed over TRIALS, not cases: a case that passes 3 of 5 trials contributes
3/5, not a boolean. Reporting a rate is the whole point of running multiple trials.
"""
import json
import pathlib
import statistics
import sys

# zai / glm-5.3 unit prices, derived from the cost block pi reports in its own trace
# (input 4746 tok -> $0.0066444; output 491 tok -> $0.0021604). Cache reads are billed
# lower but the eval artifacts do not separate them, so this over-estimates slightly.
USD_IN, USD_OUT = 1.40e-6, 4.40e-6

def summaries(root):
    for p in sorted(pathlib.Path(root).glob("*/*/*/summary.json")):
        suite = p.relative_to(root).parts[0]
        yield suite, json.loads(p.read_text())

def family(suite):
    if suite.startswith("correctness-"):
        return "correctness"
    return suite

def main():
    root = pathlib.Path(sys.argv[1])
    fam = {}
    tools, cost = [], 0.0
    rows = []

    for suite, s in summaries(root):
        f = family(suite)
        acc = fam.setdefault(f, {"pass": 0, "total": 0, "cases": 0})
        for c in s["cases"]:
            trials = c.get("trials") or []
            passed = sum(1 for t in trials if t["status"] == "passed")
            acc["pass"] += passed
            acc["total"] += len(trials)
            acc["cases"] += 1
            for t in trials:
                cost += t.get("input_tokens", 0) * USD_IN + t.get("output_tokens", 0) * USD_OUT
                if f == "consultation":
                    tools.append(t.get("command_count", 0))
            rows.append((f, c["id"], passed, len(trials), c.get("command_count", 0)))

    def rate(f):
        a = fam.get(f)
        return (a["pass"] / a["total"]) if a and a["total"] else float("nan")

    print("=" * 68)
    print("SPEC 001 SWEEP — metrics (§6)")
    print("=" * 68)
    gates = {"consultation": 0.85, "restraint": 0.90, "correctness": 0.80}
    labels = {"consultation": "Skill-open rate", "restraint": "Restraint rate",
              "correctness": "Answer accuracy"}
    for f in ("consultation", "restraint", "correctness"):
        a = fam.get(f)
        if not a:
            continue
        r = rate(f)
        verdict = "PASS" if r >= gates[f] else "BELOW GATE"
        print(f"  {labels[f]:<18} {r:6.1%}   ({a['pass']}/{a['total']} trials, "
              f"{a['cases']} cases)   gate {gates[f]:.0%} -> {verdict}")
    if tools:
        tools.sort()
        p95 = tools[min(len(tools) - 1, int(round(0.95 * (len(tools) - 1))))]
        print(f"  {'Efficiency':<18} p95 {p95} tool calls "
              f"(median {int(statistics.median(tools))}, max {max(tools)})   gate <=25")
    print(f"  {'Cost':<18} ${cost:.2f} estimated for the sweep")

    print()
    print("-" * 68)
    print("PER-CASE DETAIL (trials passed / trials run)")
    print("-" * 68)
    for f in ("consultation", "restraint", "correctness"):
        sel = [r for r in rows if r[0] == f]
        if not sel:
            continue
        print(f"\n{f}:")
        for _, cid, p, n, tc in sorted(sel, key=lambda r: (r[2] / max(r[3], 1), r[1])):
            bar = "#" * p + "." * (n - p)
            flag = "   <-- never passed" if p == 0 else ("   <-- flaky" if 0 < p < n else "")
            print(f"  {cid:<26} {p}/{n}  {bar:<6} tools={tc}{flag}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
