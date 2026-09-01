#!/usr/bin/env python3
"""Aggregate a spec-001 sweep into the four metrics of §6.

Rates are computed over TRIALS, not cases: a case that passes 3 of 5 trials contributes
3/5, not a boolean. Reporting a rate is the whole point of running multiple trials.

Cost is the vendor's own number, not an estimate. pi emits a cumulative `cost` block on
every streamed event, so summing all of them over-counts by ~100x; only `turn_end` events
are summed here. The token counts in summary.json are the LAST turn's usage, not the
trial's total, so they must not be used for cost either.
"""
import json
import pathlib
import statistics
import sys

GATES = {"consultation": 0.85, "restraint": 0.90, "correctness": 0.80}
LABELS = {"consultation": "Skill-open rate", "restraint": "Restraint rate",
          "correctness": "Answer accuracy"}
TOOL_GATE = 25


def family(suite):
    return "correctness" if suite.startswith("correctness-") else suite


def trial_cost(stdout_path):
    """Sum cost.total over turn_end events only. Returns (usd, turns)."""
    if not stdout_path.exists():
        return 0.0, 0
    usd, turns = 0.0, 0
    for line in stdout_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") != "turn_end":
            continue
        turns += 1
        stack = [ev]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                c = n.get("cost")
                if isinstance(c, dict) and isinstance(c.get("total"), (int, float)):
                    usd += c["total"]
                stack.extend(v for v in n.values() if isinstance(v, (dict, list)))
            elif isinstance(n, list):
                stack.extend(v for v in n if isinstance(v, (dict, list)))
    return usd, turns


def collect(root):
    """Walk <root>/<suite>/<timestamp>/<agent>/summary.json. Returns (fam, tools, usd, rows)."""
    root = pathlib.Path(root)
    fam, tools, rows = {}, [], []
    usd = 0.0
    for p in sorted(root.glob("*/*/*/summary.json")):
        suite = p.relative_to(root).parts[0]
        f = family(suite)
        s = json.loads(p.read_text())
        acc = fam.setdefault(f, {"pass": 0, "total": 0, "cases": 0})
        for c in s.get("cases") or []:
            trials = c.get("trials") or []
            passed = sum(1 for t in trials if t.get("status") == "passed")
            acc["pass"] += passed
            acc["total"] += len(trials)
            acc["cases"] += 1
            for t in trials:
                cusd, _ = trial_cost(p.parent / c["id"] / f"trial-{t['trial_id']}" / "stdout.txt")
                usd += cusd
                if f == "consultation":
                    tools.append(t.get("command_count") or 0)
            rows.append((f, c["id"], passed, len(trials), c.get("command_count") or 0))
    return fam, tools, usd, rows


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def main():
    root = pathlib.Path(sys.argv[1])
    fam, tools, usd, rows = collect(root)
    if not rows:
        print(f"no summary.json found under {root}", file=sys.stderr)
        return 1

    print("=" * 72)
    print("SPEC 001 SWEEP — metrics (§6)")
    print("=" * 72)
    for f in ("consultation", "restraint", "correctness"):
        a = fam.get(f)
        if not a or not a["total"]:
            continue
        r = a["pass"] / a["total"]
        verdict = "PASS" if r >= GATES[f] else "BELOW GATE"
        print(f"  {LABELS[f]:<18} {r:6.1%}   ({a['pass']}/{a['total']} trials, "
              f"{a['cases']} cases)   gate {GATES[f]:.0%} -> {verdict}")
    if tools:
        v = p95(tools)
        verdict = "PASS" if v <= TOOL_GATE else "BELOW GATE"
        print(f"  {'Efficiency':<18} p95 {v:>4} tool calls   "
              f"(median {int(statistics.median(tools))}, max {max(tools)})"
              f"   gate <={TOOL_GATE} -> {verdict}")
    n_trials = sum(a["total"] for a in fam.values())
    print(f"  {'Cost':<18} ${usd:.2f} over {n_trials} trials "
          f"(${usd / max(n_trials, 1):.4f}/trial)   reported, not gated")

    print()
    print("-" * 72)
    print("PER-CASE DETAIL (trials passed / trials run)")
    print("-" * 72)
    for f in ("consultation", "restraint", "correctness"):
        sel = [r for r in rows if r[0] == f]
        if not sel:
            continue
        print(f"\n{f}:")
        for _, cid, p, n, tc in sorted(sel, key=lambda r: (r[2] / max(r[3], 1), r[1])):
            bar = "#" * p + "." * (n - p)
            flag = "   <-- never passed" if p == 0 else ("   <-- flaky" if p < n else "")
            print(f"  {cid:<26} {p}/{n}  {bar:<6} tools={tc}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
