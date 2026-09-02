# Evals

Two suites live here. They answer different questions and neither replaces the other.

| | `prompts.csv` + `checks.toml` (v1) | `v2/` (spec 001) |
|---|---|---|
| Question | does the skill still trigger at all? | how well does it actually perform? |
| Cases | 14, all positive | 42 — 22 consultation, 8 restraint, 12 correctness |
| Trials per case | 1 | 5 |
| Agents | `claude` only | any (baselined on `pi`) |
| Wired into CI | yes — `eval validate` + `eval score` on every PR | no, runs on demand |
| Cost per run | $0 (deterministic jobs) | ~$6, ~1 h |

v1 is the smoke test the release pipeline depends on. v2 is the measurement. Run v1 before
every PR — CI does it for you. Run v2 when you change `SKILL.md` in a way that could move
behaviour, and compare against the committed baseline.

```
evals/
├── prompts.csv               # v1 cases — referenced by [tool.fastskill.eval]
├── checks.toml               # v1 global checks
├── fixtures/{pass,fail}/     # recorded runs, for offline `eval score` in CI
├── agent-eval.Dockerfile     # reproducible container for a live v1 run
└── v2/                       # spec 001 suite — see v2/README.md
```

## Running v1

`fastskill` resolves `../evals/` relative to the manifest, so the first two commands run
from `fastskill/` and the fixture check runs from the repo root.

```bash
cd fastskill
fastskill eval validate                                   # schema + config, no agent
cd ..
fastskill eval score --run-dir evals/fixtures/pass        # must exit 0
fastskill eval score --run-dir evals/fixtures/fail        # must exit non-zero

cd fastskill                                              # live run: needs an agent + key
fastskill eval run --agent claude --output-dir ../eval-runs
fastskill eval report --run-dir ../eval-runs/<timestamp>/claude
```

`eval score` is not read-only: it backfills `command_count` and the token counts into the
run's `summary.json` from the trial artifacts. Scoring the committed fixtures therefore
dirties the tree — restore them with `git show HEAD:<path> > <path>` before committing.
CI is unaffected; it never commits the checkout.

v1's `skill_invoked` check needs a structured `Skill` tool-use event in the trace. Only
Claude Code emits one, so a live v1 run against any other agent fails the suite by
construction — that is not a regression.

## Running v2

```bash
python3 evals/v2/guard_vacuity.py         # must pass before you trust any number
./evals/v2/run.sh pi ./eval-runs/v2 5     # 42 cases x 5 trials, ~1 h, ~$6
python3 evals/v2/aggregate.py ./eval-runs/v2
```

`run.sh` runs the guard itself as a hard precondition, stages a throwaway skill tree and
manifest per suite, and leaves the repo's own manifest untouched. The suites are generated
— edit `v2/patterns.json` and re-run `python3 evals/v2/build.py`, never the `checks.toml`
files.

Raw artifacts are gitignored (`/eval-runs/`) — only the aggregated result is committed, as
[`v2/baseline/pi-glm-5.3-2026-09-01.txt`](v2/baseline/pi-glm-5.3-2026-09-01.txt).
Internals and per-suite detail: [`v2/README.md`](v2/README.md). Design rationale:
[`specs/001-enhanced-eval.md`](../specs/001-enhanced-eval.md).

## Methodology

### Every oracle must be able to fail

An eval is worthless if its checks pass regardless of what the agent did. Three properties
of this engine make that easy to get wrong, and all three bit during authoring:

1. **The haystack contains the skill.** Text checks substring-match the whole trace, and
   the trace echoes every file the agent read — `SKILL.md` included. So any pattern that
   appears in the skill document matches the moment the agent opens it, whatever it
   answered. `v2/guard_vacuity.py` scans the skill payload and fails if any pattern occurs
   there. It caught `--enable-write`, `--local` and `--scope project`.
2. **Checks are global.** One `checks.toml` applies to every case in a suite; there is no
   per-case dispatch. Distinct expectations therefore need distinct suites, which is why
   v2 has one directory per correctness assertion.
3. **`should_trigger` is not scored.** It is parsed and carried into the case, then never
   read by any check. A case marked `should_trigger = false` asserts nothing on its own —
   the negative has to be expressed as a check with `expected = false`.

The consequence for writing a positive check: pair a real flag with a value invented for
that prompt. `--tag` is vacuous; `--tag v2.1.0` can only come from the agent synthesizing
an answer.

### Rates over trials, not cases

A single trial cannot distinguish "reliable" from "got lucky". v2 runs 5 trials per case
and reports passing *trials* over total, so a case that passes 3 of 5 contributes 0.6
rather than a boolean. Per-case output flags anything between 0 and 5 as flaky.

### Dead trials are excluded

A provider timeout produces a trial with a complete-looking artifact set and zero model
output. Such a trial **passes every negative oracle**, because an absent pattern is
absent — an outage would score as perfect restraint. `aggregate.py` classifies a trial as
dead when its trace carries no assistant message text, drops it from every rate, and
reports the count separately.

The discriminator is assistant text, not tool calls: a restraint trial correctly makes
zero tool calls and still answers at length. In the baseline sweep 4 of 210 trials were
dead, and they were the entire gap between a reported 96.4% and the true 100%.

### One metric per check

A consultation trial carries two required checks. Folding them into a single suite
pass-rate reports a tool-budget overrun as a recall failure, so each metric names the
exact check it aggregates. `aggregate.py` warns if any observed check is claimed by no
metric — that guard exists because an earlier version silently measured 1 of 12
correctness cases.

| Metric | Checks | Gate | Baseline (pi / glm-5.3) |
|---|---|---|---|
| Skill-open rate | consultation `trigger_expectation` | ≥ 0.85 | 100.0% (106/106) |
| Restraint rate | restraint `trigger_expectation` | ≥ 0.90 | 100.0% (40/40) |
| Answer accuracy | correctness `command_contains` + `trigger_expectation` | ≥ 0.80 | 96.7% (58/60) |
| Tool-budget compliance | consultation `max_tool_calls` | ≥ 0.90 | 92.5% (98/106) |
| Efficiency | p95 tool calls per consultation trial | ≤ 25 | 30 (median 8, max 50) |
| Cost | USD per sweep | not gated | $5.81 / 210 trials |

Gates are ratified against the first baseline, not asserted in advance. The efficiency
gate is deliberately left unmet — retuning a threshold to fit its own observation makes it
unfalsifiable.

### Cost is the vendor's number

`aggregate.py` sums `cost.total` from `turn_end` events in the agent's stdout. It does not
estimate from token counts: `summary.json` records the *last* turn's usage, not the
trial's total. `pi` also re-emits a cumulative cost block on every streamed event, so
summing all of them over-counts by roughly 100x.

## Verifying the measurement itself

No agent needed, seconds to run:

```bash
python3 evals/v2/guard_vacuity.py                     # no oracle can pass vacuously
python3 evals/v2/test_aggregate.py                    # metrics match hand-computed answers
evals/v2/negctl.sh ./eval-runs/v2/consultation/<timestamp>/pi   # needs one real run
```

`negctl.sh` is the red-green proof: it copies a real completed case, deletes the trace
line carrying the skill read from one copy, and re-scores both. The consultation oracle
must go from pass to fail while `max_tool_calls` stays put.

## Adding a case

**To v1** — append a row to `prompts.csv`. It must be positive; the global `skill_invoked`
check applies to it. Keep the suite small: it runs on the release path.

**To v2** — edit `v2/patterns.json`, then `python3 evals/v2/build.py` and
`python3 evals/v2/guard_vacuity.py`. A correctness pattern that the guard rejects is
telling you the phrase already appears in `SKILL.md`, so matching it would prove nothing;
pick a value the agent has to synthesize instead.

## CI

`.github/workflows/skill-evals.yml`:

- **validate** and **score-fixtures** — required checks, every PR, deterministic, no tokens.
- **live-eval** — opt-in via *Run workflow*, v1 only, needs `OPENAI_API_KEY` /
  `ANTHROPIC_API_KEY`.

Nothing in CI runs v2. At ~$6 and ~1 h a sweep it belongs on a schedule or a manual
trigger, not on a pull request, and no job enforces the gates above yet.
