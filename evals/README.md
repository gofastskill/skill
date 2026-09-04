# Evals

Two suites live here. They answer different questions and neither replaces the other.

| | `prompts.csv` + `checks.toml` (v1) | `v2/` (spec 001) |
|---|---|---|
| Question | does the skill still trigger at all? | how well does it actually perform? |
| Cases | 14, all positive | 42 — 22 consultation, 8 restraint, 12 correctness |
| Trials per case | 1 | 5 |
| Agents | `claude` only | any (baselined on `pi`) |
| Judged by an LLM | no | one advisory judge, on correctness |
| Wired into CI | yes — `eval validate` + `eval score` on every PR | the suites are validated on every PR; the sweep runs on demand |
| Cost per run | $0 (deterministic jobs) | ~$6 for the agent, ~1 h, plus one judge call per correctness trial |

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
    ├── stage.sh              # one suite → a throwaway skill tree; used by run.sh and CI
    └── correctness/judge-prompt.md   # the judge's rubric prompt, hand-written
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

`eval score` is read-only. Every number it reports is a function of the run's artifacts,
and scoring the committed fixtures leaves the tree clean. The backfill of `command_count`
and the token counts now happens in `eval run`, at write time, where the writer owns the
artifact it is writing.

v1's `skill_invoked` check counts two shapes: a tool use named `Skill`, which only Claude
Code emits, and any tool use whose input references the skill document's path. A live v1
run against another agent is therefore scoreable, provided that agent's decoder emits
tool-use frames at all.

## Running v2

```bash
python3 evals/v2/guard_vacuity.py         # must pass before you trust any number

export AIKIT_LLM_URL=https://…/v1         # the judge's endpoint — there is no default
export JUDGE_API_KEY=…                    # its key, named by api_key_env in checks.toml
export JUDGE_MODEL=glm-5.3                # optional; overrides the model checks.toml declares
./evals/v2/run.sh pi ./eval-runs/v2 5     # 42 cases x 5 trials, ~1 h, ~$6 + the judge's calls
```

`run.sh` runs the guard itself as a hard precondition, stages a throwaway skill tree and
manifest per suite via `v2/stage.sh`, leaves the repo's own manifest untouched, and finishes
by folding all three runs into the metrics in `v2/metrics.toml`. The suites are generated —
edit `v2/patterns.json` and re-run `python3 evals/v2/build.py`, never the `checks.toml`
files. The one exception is `v2/correctness/judge-prompt.md`, which is prose and is written
by hand.

The correctness suite declares a judge, so it runs with `--judge` and needs the two variables
above. `run.sh` checks for them before the first suite starts: correctness runs last, and a
key missing at its turn would surface only after the other two had been paid for in full.

To re-fold a sweep already on disk without re-running it:

```bash
fastskill eval scorecard --root ./eval-runs/v2 --metrics evals/v2/metrics.toml
```

Raw artifacts are gitignored (`/eval-runs/`) — only the folded result is committed, as
[`v2/baseline/pi-glm-5.3-2026-09-01.txt`](v2/baseline/pi-glm-5.3-2026-09-01.txt).
Internals and per-suite detail: [`v2/README.md`](v2/README.md). Design rationale:
[`specs/001-enhanced-eval.md`](../specs/001-enhanced-eval.md).

## Methodology

### Every check must be able to fail

An eval is worthless if its checks pass regardless of what the agent did. Three properties
of this engine made that easy to get wrong, and all three bit during authoring. One is
inherent and two have since been fixed:

1. **The haystack contains the skill.** Text checks substring-match the whole trace, and
   the trace echoes every file the agent read — `SKILL.md` included. So any pattern that
   appears in the skill document matches the moment the agent opens it, whatever it
   answered. `v2/guard_vacuity.py` scans the skill payload and fails if any pattern occurs
   there. It caught `--enable-write`, `--local` and `--scope project`. This one is
   inherent to text matching and the guard is the answer to it.
2. **Checks used to be global.** One `checks.toml` applied to every case in a suite, so
   distinct expectations needed distinct suites — which is why v2 once had one directory
   per correctness assertion. `[[check]]` entries now take a `cases` list, and the twelve
   directories collapsed into one suite.
3. **`should_trigger` used to be unscored.** It was parsed, carried into the case, and read
   by no check, so a case marked `false` asserted nothing while every reader of the CSV
   assumed otherwise. It now generates a `skill_invoked` check with matching polarity, and
   a case whose explicit checks contradict the column is rejected rather than silently
   resolved.

The consequence for writing a positive check: pair a real flag with a value invented for
that prompt. `--tag` is vacuous; `--tag v2.1.0` can only come from the agent synthesizing
an answer.

### A substring check cannot see the command around it

`command_contains` matches the substring it was given and nothing around it. The correctness
case for `marketplace create` requires `--base-url https://cdn.acme.io/skills/`, and this
answer contains it:

```
fastskill marketplace create --path ./team-skills --base-url https://cdn.acme.io/skills/
```

That command does not run: `--path` is not a fastskill argument, the directory is positional,
and the binary rejects the invocation before doing anything. The check passes regardless.

The correctness suite therefore also carries one LLM judge, `command-correctness`, which
scores each answer against a reference answer in the `expected` column of `prompts.csv`. Its
`would_run` criterion asks exactly the question the substring cannot. The judge is advisory —
it declares no `min_score`, so it moves no verdict, and its two metrics report at
`min_rate`/`min_score` `0.0`. See [`v2/README.md`](v2/README.md#the-judge).

The reference answer reaches the judge and nothing else. The runner sends the agent
`case.prompt` alone, so an `expected` column cannot leak the answer into the trace it is
being used to grade.

### Rates over trials, not cases

A single trial cannot distinguish "reliable" from "got lucky". v2 runs 5 trials per case
and reports passing *trials* over total, so a case that passes 3 of 5 contributes 0.6
rather than a boolean. Per-case output flags anything between 0 and 5 as flaky.

### Trials with outcome `error` are excluded

A provider timeout produces a trial with a complete-looking artifact set and zero model
output. Such a trial **passes every negative expectation**, because an absent pattern is
absent, and passes every tool-call ceiling, because zero is under every limit — so an
outage scores as perfect restraint and perfect budget compliance. The same outage on a
positive suite scores as total failure. The direction of the lie is set by the polarity of
the check, which is why no single default is safe and such a trial must be excluded rather
than reduced to a pass or averaged in as a wrong answer.

The engine decides this on transport and terminal signal, not on the content of the
output: a non-zero exit, a timeout, the agent's own terminal event reporting failure, or a
stream that ended with no terminal event on a backend that declares it emits one. An agent
that exits cleanly having answered with nothing is a **failure**, not an error — that is a
real skill failure and scores as one.

`pass_rate` is over scored trials, and the excluded count travels on the case rather than
being dropped. A case whose every trial errored has no scored trials at all: it takes the
verdict `error`, is left out of the split score, and `eval score` exits non-zero naming
it, because silent exclusion would move the same hazard up one level.

In the baseline sweep 4 of 210 trials errored, and they were the entire gap between a
reported 96.4% and the true 100%. They were detected then by a text heuristic in a Python
post-processor, which was a workaround for evidence the engine was discarding: the agent's
stdout carried `"stopReason":"error"` sixteen times and trace normalization kept none of
it. The engine now records it.

### One metric per check

A consultation trial carries two required checks. Folding them into a single suite
pass-rate reports a tool-budget overrun as a recall failure, so each metric names the
exact check type it folds. Metrics are declared in [`v2/metrics.toml`](v2/metrics.toml)
and applied by `fastskill eval scorecard`, which selects cases by `*`-wildcard id pattern
rather than by the directory a suite happens to live in.

| Metric | Checks | Gate | Baseline (pi / glm-5.3) |
|---|---|---|---|
| Skill-open rate | `op-*` `skill_invoked` | ≥ 0.85 | 100.0% (106/106) |
| Restraint rate | `off-*` `skill_invoked` | ≥ 0.90 | 100.0% (40/40) |
| Answer accuracy | `c-*` `command_contains` + `trigger_expectation` | ≥ 0.80 | 96.7% (58/60) |
| Tool-budget compliance | `op-*` `max_tool_calls` | ≥ 0.90 | 92.5% (98/106) |
| Efficiency | p95 tool calls per `op-*` trial | ≤ 25 | 30 (median 8, max 50) |
| Cost | USD per sweep | not gated | $5.81 / 210 trials |
| Command-correctness judgment | judge `overall` over `c-*` | not gated | not yet measured |
| Command would run as written | judge `would_run` over `c-*` | not gated | not yet measured |

The baseline predates the collapse to three suites, so its consultation and restraint
figures were measured by the text check that `skill_invoked` replaced. It also predates the
judge, which is why the two judgment rows have no figure: no sweep has been run with
`--judge` yet, and a scorecard cannot be back-filled with judgments the run never made. Two further check
results the sweep now produces — skill invocation and tool budget on the correctness
prompts — are claimed by `metrics.toml` at `min_rate = 0.0`, which reports them without
gating them. There is no baseline to set a real bar from yet, and inventing one would make
an unmeasured threshold look like an agreed one.

Gates are ratified against the first baseline, not asserted in advance. The efficiency
gate is deliberately left unmet — retuning a threshold to fit its own observation makes it
unfalsifiable.

Two guards sit on the metrics themselves. A metric matching no observed check result
**fails the command**, and `--no-fail` does not suppress it, because a mistyped case
pattern would otherwise make a gate quietly disappear. And check results that no metric
claims are named in a warning — that guard exists because an earlier version silently
measured 1 of 12 correctness cases.

### Cost is the vendor's number

Each trial records the cost its backend reported, and the scorecard sums that field.
Absent it, the trial records nothing and the report reads "not reported". Cost is never
estimated from a local price table or from token counts: `summary.json` records the *last*
turn's usage rather than the trial's total, `pi` re-emits a cumulative cost block on every
streamed event so summing them over-counts by roughly 100x, and a stale estimate is
indistinguishable from a real number once it reaches a report.

## Verifying the measurement itself

No agent needed, seconds to run:

```bash
python3 evals/v2/guard_vacuity.py                     # no check can pass on a mere read
evals/v2/negctl.sh ./eval-runs/v2/consultation/<timestamp>/pi   # needs one real run
```

`negctl.sh` is the red-green proof: it copies a real completed case, deletes the trace
line carrying the skill read from one copy, and re-scores both. The consultation check
must go from pass to fail while `max_tool_calls` stays put. It reads the path to delete
out of each trial's `result.json`, so it removes the evidence the check actually reads.

## Adding a case

**To v1** — append a row to `prompts.csv`. It must be positive; the global `skill_invoked`
check applies to it. Keep the suite small: it runs on the release path.

**To v2** — edit `v2/patterns.json`, then `python3 evals/v2/build.py` and
`python3 evals/v2/guard_vacuity.py`. A correctness pattern that the guard rejects is
telling you the phrase already appears in `SKILL.md`, so matching it would prove nothing;
pick a value the agent has to synthesize instead. A correctness case also needs an
`expected` field — one correct response, written the way you would answer the prompt — which
becomes the `expected` column and the judge's reference. The guard does not scan it: it is
never matched against a trace.

## CI

`.github/workflows/skill-evals.yml`:

- **validate** and **score-fixtures** — required checks, every PR, deterministic, no tokens.
  Both are v1: `validate` reads the manifest's own eval section, which names nothing under
  `evals/v2`.
- **validate-v2** — every PR, deterministic, no tokens. Regenerates the suites and fails if
  they differ from what is committed, runs the vacuity guard, then stages each suite through
  `v2/stage.sh` and runs `eval validate` on it. That last step is what checks the judge:
  `eval validate` parses the judge and its prompt without calling anything. Advisory, not a
  required check — requiring one is a repository setting, and a required check that has never
  reported blocks every open pull request.
- **live-eval** — opt-in via *Run workflow*, v1 only, needs `OPENAI_API_KEY` /
  `ANTHROPIC_API_KEY`.

No CI job runs a v2 *sweep*. At ~$6 and ~1 h it belongs on a schedule or a manual trigger,
not on a pull request, and no job enforces the gates above yet.
