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


def is_alive(trace_path):
    """Did the agent actually produce an answer?

    A provider timeout or connection error yields a trial with a normal-looking
    artifact set and zero model output. Such a trial silently PASSES every negative
    oracle -- an absent pattern is absent -- so an outage would read as perfect
    restraint and perfect tool-budget compliance. Dead trials are excluded from every
    rate and reported separately.

    The discriminator is assistant text, not tool calls: a restraint trial correctly
    makes zero tool calls and still answers at length.
    """
    if not trace_path.exists():
        return False
    for line in trace_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        pl = ev.get("payload") or {}
        if pl.get("type") == "message" and pl.get("role") != "system" and pl.get("text"):
            return True
    return False


def collect(root):
    """Walk <root>/<suite>/<timestamp>/<agent>/summary.json.

    Returns (checks, tools, usd, rows) where `checks` is keyed by (family, check_name)
    so each oracle gets its own rate. A consultation trial carries two required checks
    and folding them into one suite pass-rate would report a tool-budget overrun as a
    recall failure.
    """
    root = pathlib.Path(root)
    checks, tools, rows, dead = {}, [], [], []
    usd = 0.0
    for p in sorted(root.glob("*/*/*/summary.json")):
        suite = p.relative_to(root).parts[0]
        f = family(suite)
        s = json.loads(p.read_text())
        for c in s.get("cases") or []:
            trials = c.get("trials") or []
            tc, fail_by, n_dead = [], {}, 0
            for t in trials:
                td = p.parent / c["id"] / f"trial-{t['trial_id']}"
                cusd, _ = trial_cost(td / "stdout.txt")
                usd += cusd
                if not is_alive(td / "trace.jsonl"):
                    n_dead += 1
                    dead.append((f, c["id"], t["trial_id"]))
                    continue
                n = t.get("command_count") or 0
                tc.append(n)
                if f == "consultation":
                    tools.append(n)
                for ck in t.get("check_results") or []:
                    acc = checks.setdefault((f, ck["check_name"]),
                                            {"pass": 0, "total": 0, "cases": set()})
                    acc["total"] += 1
                    acc["pass"] += bool(ck["passed"])
                    acc["cases"].add(c["id"])
                    if not ck["passed"]:
                        fail_by[ck["check_name"]] = fail_by.get(ck["check_name"], 0) + 1
            live = [t for t in trials if t.get("status") is not None]
            passed = sum(1 for t in trials if t.get("status") == "passed")
            rows.append({"family": f, "id": c["id"], "passed": passed,
                         "total": len(trials), "dead": n_dead,
                         "mean_tools": (sum(tc) / len(tc)) if tc else 0.0,
                         "max_tools": max(tc) if tc else 0, "fail_by": fail_by})
    return checks, tools, usd, rows, dead


METRICS = [
    ("consultation", {"trigger_expectation"}, "Skill-open rate", 0.85),
    ("restraint", {"trigger_expectation"}, "Restraint rate", 0.90),
    ("correctness", {"command_contains", "trigger_expectation"}, "Answer accuracy", 0.80),
    ("consultation", {"max_tool_calls"}, "Tool-budget compliance", 0.90),
]


def metric(checks, fam, names):
    """Fold the named checks of one family. Returns (passed, total, n_cases)."""
    accs = [checks[(fam, n)] for n in sorted(names) if (fam, n) in checks]
    if not accs:
        return 0, 0, 0
    return (sum(a["pass"] for a in accs),
            sum(a["total"] for a in accs),
            len(set().union(*(a["cases"] for a in accs))))


def orphans(checks):
    """Observed assertion checks that no metric claims -- i.e. silently unreported."""
    claimed = {(f, n) for f, names, _, _ in METRICS for n in names}
    return sorted(k for k in checks if k not in claimed and k[1] != "max_tool_calls")


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def main():
    root = pathlib.Path(sys.argv[1])
    checks, tools, usd, rows, dead = collect(root)
    if not rows:
        print(f"no summary.json found under {root}", file=sys.stderr)
        return 1

    orph = orphans(checks)
    if orph:
        print("WARNING: check results not covered by any metric: "
              + ", ".join(f"{f}/{n}" for f, n in orph))

    print("=" * 74)
    print("SPEC 001 SWEEP - metrics (S6)")
    print("=" * 74)
    for fam, names, label, gate in METRICS:
        ok, tot, ncases = metric(checks, fam, names)
        if not tot:
            continue
        r = ok / tot
        verdict = "PASS" if r >= gate else "BELOW GATE"
        print(f"  {label:<24} {r:6.1%}   ({ok}/{tot} trials, "
              f"{ncases} cases)   gate {gate:.0%} -> {verdict}")
    if tools:
        v = p95(tools)
        verdict = "PASS" if v <= TOOL_GATE else "BELOW GATE"
        print(f"  {'Efficiency (p95 tools)':<24} {v:6}   "
              f"(median {int(statistics.median(tools))}, max {max(tools)}, "
              f"n={len(tools)})   gate <={TOOL_GATE} -> {verdict}")
    if dead:
        by_case = {}
        for _, cid, _ in dead:
            by_case[cid] = by_case.get(cid, 0) + 1
        print(f"  {'Dead trials':<24} {len(dead):6}   excluded from every rate above "
              f"({', '.join(f'{k} x{v}' for k, v in sorted(by_case.items()))})")
    n = sum(r["total"] for r in rows)
    print(f"  {'Cost':<24} ${usd:6.2f}   over {n} trials "
          f"(${usd / max(n, 1):.4f}/trial)   reported, not gated")

    print()
    print("-" * 74)
    print("PER-CASE DETAIL   (trials passed/run, mean tool calls per trial)")
    print("-" * 74)
    for f in ("consultation", "restraint", "correctness"):
        sel = [r for r in rows if r["family"] == f]
        if not sel:
            continue
        print(f"\n{f}:")
        for r in sorted(sel, key=lambda r: (r["passed"] / max(r["total"], 1), r["id"])):
            scored = r["total"] - r["dead"]
            bar = "#" * r["passed"] + "." * (scored - r["passed"]) + "x" * r["dead"]
            why = ""
            if r["dead"]:
                why += f"  [{r['dead']} dead]"
            if r["fail_by"]:
                why += "  <- " + ", ".join(f"{k} x{v}" for k, v in sorted(r["fail_by"].items()))
            print(f"  {r['id']:<24} {r['passed']}/{scored}  {bar:<6} "
                  f"tools mean {r['mean_tools']:5.1f} max {r['max_tools']:3}{why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
