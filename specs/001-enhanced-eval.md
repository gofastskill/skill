# Spec 001 — Enhanced eval suite for the fastskill skill

Status: proposed
Author: Alexandre Oliveira
Date: 2026-09-01
Target agent for the reference measurement: `pi` (zai / glm-5.3)

## 1. Why the current suite is not a performance measurement

`evals/prompts.csv` holds 14 cases and `evals/checks.toml` holds two checks:

```toml
[[check]]
name = "skill_invoked"
skill = "fastskill"
expected = true
required = true

[[check]]
name = "max_tool_calls"
limit = 100
required = true
```

Four properties make this a smoke test rather than a measurement.

1. **One trial per case at a 1.0 threshold.** Agent behaviour is stochastic. A single
   sample cannot distinguish a skill that is consulted nine times out of ten from one
   consulted half the time, yet any single miss fails the suite. The signal is noise.
2. **No negative cases.** Every row asserts the skill should be used. Over-triggering —
   the skill hijacking unrelated prompts — is invisible, and it is the more expensive
   failure in daily use because it taxes every unrelated conversation.
3. **No correctness oracle.** Both checks are structural. A run where the agent loads the
   skill and then gives wrong advice scores identically to one where it gives right advice.
4. **The tool-call ceiling never binds.** Observed usage ranges from 2 to 31 calls against
   a limit of 100, so the check cannot fail and contributes nothing.

## 2. Engine constraints this spec must design around

These were established by reading the pinned `aikit-evals` source and by instrumenting a
live `pi` run. They are not preferences; they bound what any suite in this repo can assert.

### C1 — Checks are global, never per case

`run_checks(checks, _stdout, trace_jsonl, working_dir)` maps one check list over every
case. There is no per-case dispatch anywhere in `aikit-evals/src/checks.rs`.

> **Consequence:** a suite can only express *one* expectation shape. Cases needing
> different expectations must live in *different suites*, each with its own
> `prompts.csv` + `checks.toml`, run separately.

### C2 — `should_trigger` in the CSV is documentation only

```rust
/// Whether the skill should trigger (documentation-only; checks.toml is authoritative)
pub should_trigger: bool,
```

It is parsed into `EvalCase` and never consulted for pass/fail. Negative expectations
must be encoded as a check, not as a CSV column.

### C3 — `skill_invoked` does not work for every agent

`skill_invoked` scans the trace for a `tool_use` whose `tool_name` is exactly `Skill`.
`pi` has no such tool: it loads skills via `--no-skills --skill <path>` and exposes only
`read`, `bash`, `edit`, `write`. A live probe confirms it — the single case run against
`pi` produced tool names `{read: 1}` and the check reported
`Skill invocation 'fastskill' not found` while the answer was fully correct.

> **Consequence:** for `pi`, skill consultation must be detected as a `read` of the
> materialized skill path, not as a `Skill` tool call.

### C4 — The text haystack contains the skill document itself

`trigger_expectation` and `command_contains` substring-match against `pattern_haystack`,
which is the whole trace JSONL with only `Unknown` payload `raw` fields blanked. Measured
composition of a real `pi` trace:

| Content | In haystack? |
|---|---|
| The user prompt | No |
| `SKILL.md` body, echoed by the agent's `read` tool_result | **Yes** |
| The agent's streamed answer text and reasoning | Yes |
| The final `result` payload | No — its `raw` is blanked |

> **Consequence — the vacuity rule.** Any pattern that occurs in `SKILL.md` will match as
> soon as the agent opens the file, regardless of what it answered. Such a check is an
> oracle that cannot fail. **Every text pattern in this suite MUST be verified absent from
> `SKILL.md`.** This is enforced mechanically by `evals/v2/guard_vacuity.py`, which fails
> the build if any pattern is a substring of the skill document.

### C5 — Suite paths come only from the manifest

`eval run` has no flag to override `prompts` / `checks`; they are read from
`[tool.fastskill.eval]`. Running several suites therefore requires several manifests. The
runner stages a throwaway skill tree per suite outside the repo rather than mutating the
tracked `skill-project.toml`.

## 3. Design principles

- **P1 — One oracle per suite.** Forced by C1, but also good practice: a suite reports one
  number that means one thing.
- **P2 — Non-vacuous oracles only.** Every pattern is proven absent from `SKILL.md` (C4).
  Positive patterns are made *scenario-unique*: they pair a real fastskill flag with a
  value invented for that prompt, so the string can only exist if the agent synthesized an
  answer for that scenario. `--tag` alone is vacuous; `--tag v2.1.0` is not.
- **P3 — Measure both directions.** Recall without precision is meaningless. Every
  positive suite is paired with a restraint suite that asserts the skill is *not* consulted
  on off-topic prompts.
- **P4 — Repeat, then report a rate.** Five trials per case. Report the rate, not a
  boolean. Gate on the rate.
- **P5 — Prefer outcome oracles to text oracles** where the operation produces an artifact,
  because a file either exists or it does not and no amount of echoing can fake it.
- **P6 — Measurement runs do not gate.** The reference run uses `--no-fail` and aggregates
  externally. Thresholds in §6 are for CI, applied once a baseline exists.

## 4. Suite architecture

```
evals/v2/
├── consultation/         one suite, N cases   — does the skill get opened when it should?
│   ├── prompts.csv
│   └── checks.toml
├── restraint/            one suite, N cases   — is it left alone when it should be?
│   ├── prompts.csv
│   └── checks.toml
├── correctness/          one suite PER assertion (C1)
│   ├── <case-id>/prompts.csv
│   └── <case-id>/checks.toml
├── patterns.json         single source of truth for every pattern; guard input
├── guard_vacuity.py      fails if any pattern occurs in SKILL.md
└── run.sh                stages manifests, runs all suites, aggregates
```

### 4.1 Consultation suite

Covers the main operations of the CLI, one case per operation, phrased as a user would.

Checks:

```toml
[[check]]
name = "trigger_expectation"
pattern = "skills/fastskill/SKILL.md"
expected = true
required = true

[[check]]
name = "max_tool_calls"
limit = 25
required = true
```

The pattern is the materialized skill path as it appears in the agent's `read` tool_use
input. It is absent from `SKILL.md`, so it is non-vacuous per C4. The limit is set to 25
against an observed maximum of 31 so that it is a live efficiency constraint rather than
decoration; cases that legitimately need more will surface as failures to be triaged.

Metric: **skill-open rate**. Named for what it measures — the agent opened the full skill
document. An agent answering correctly from the injected description alone scores as a
miss; this is a known conservative bias, recorded in §7.

### 4.2 Restraint suite

Off-topic prompts that must not pull the skill in. Same pattern, inverted.

```toml
[[check]]
name = "trigger_expectation"
pattern = "skills/fastskill/SKILL.md"
expected = false
required = true
```

Metric: **restraint rate**. An empty trace counts as a run failure, not a pass, so this
check cannot be satisfied vacuously by an agent that never started.

### 4.3 Correctness suites

One directory per assertion. Each prompt embeds a value invented for that scenario; the
check requires the flag and that value together.

Metric: **answer accuracy**.

## 5. Case inventory

### Consultation (on-topic, expect the skill to be opened)

| id | operation |
|---|---|
| `op-init` | `init` |
| `op-add-git` | `add` from git |
| `op-add-editable` | `add -e` |
| `op-add-recursive` | `add -r` |
| `op-install-manifest` | `install` |
| `op-install-lock` | `install --lock` |
| `op-list` | `list` |
| `op-read` | `read` |
| `op-remove` | `remove` |
| `op-update` | `update` |
| `op-reindex` | `reindex` |
| `op-search` | `search` |
| `op-repos-add` | `repos add` |
| `op-repos-browse` | `repos skills` / `show` |
| `op-marketplace` | `marketplace create` |
| `op-analyze` | `analyze duplicates` |
| `op-optimize` | `optimize run` |
| `op-serve` | `serve` |
| `op-mcp` | `mcp install` |
| `op-doctor` | `doctor` |
| `op-eval` | `eval run` |
| `op-auth` | repository authentication model |

### Restraint (off-topic, expect the skill to be left alone)

| id | why it is off topic |
|---|---|
| `off-python-list` | a Python language question |
| `off-git-rebase` | a git question |
| `off-docker` | a Dockerfile question |
| `off-sql` | a SQL query question |
| `off-npm` | a *different* package manager |
| `off-pip` | another different package manager |
| `off-regex` | a regex question |
| `off-k8s` | a Kubernetes question |

`off-npm` and `off-pip` are the sharp ones: they are package-manager questions, which is
the nearest neighbour to fastskill's own domain and the likeliest source of a false trigger.

### Correctness (scenario-unique oracles)

| suite id | scenario value | required pattern(s) |
|---|---|---|
| `c-tag-pin` | tag `v2.1.0` | `--tag v2.1.0` |
| `c-branch-pin` | branch `release-42` | `--branch release-42` |
| `c-group-add` | group `qa` | `--group qa` |
| `c-install-only` | group `staging` | `--only staging` |
| `c-install-without` | group `docs` | `--without docs` |
| `c-serve-port` | port `9123`, writes on | `--port 9123`, `--enable-write` |
| `c-search-limit` | limit `3`, local, json | `--limit 3`, `--local` |
| `c-analyze-threshold` | threshold `0.97` | `--threshold 0.97` |
| `c-marketplace-baseurl` | base URL `https://cdn.acme.io/skills/` | `--base-url https://cdn.acme.io/skills/` |
| `c-mcp-cursor` | agent cursor, project scope | `--agent cursor`, `--scope project` |
| `c-repos-priority` | priority `7` | `--priority 7` |
| `c-no-publish` | asks for a nonexistent publish flow | must **not** contain `fastskill publish` |

`c-no-publish` is a hallucination guard: the CLI has no `publish` command, and `SKILL.md`
says so. The literal string `fastskill publish` is absent from the document, so an
occurrence can only be the agent inventing it.

## 6. Metrics and acceptance thresholds

Reported per agent, five trials per case. Each metric names the exact check it
aggregates: a consultation trial carries two required checks, and folding them into one
suite pass-rate would report a tool-budget overrun as a recall failure.

| Metric | Checks aggregated | Gate | Baseline (pi / glm-5.3) |
|---|---|---|---|
| Skill-open rate | consultation `trigger_expectation` | ≥ 0.85 | **100.0%** (106/106) |
| Restraint rate | restraint `trigger_expectation` | ≥ 0.90 | **100.0%** (40/40) |
| Answer accuracy | correctness `command_contains` + `trigger_expectation` | ≥ 0.80 | **96.7%** (58/60) |
| Tool-budget compliance | consultation `max_tool_calls` | ≥ 0.90 | **92.5%** (98/106) |
| Efficiency | p95 tool calls per consultation trial | ≤ 25 | **30** (median 8, max 50) |
| Cost | USD per full sweep | reported, not gated | **$5.81** / 210 trials |

Baseline measured 2026-09-01, 42 cases x 5 trials, commit `a10df77`.

Thresholds were proposals to be ratified against the first baseline, not asserted in
advance. Gating before a baseline exists is how a suite gets disabled. Ratified: the four
rate gates hold and stay as written. The efficiency gate does **not** hold and is
deliberately left at 25 — see §7.6.

### 6.1 Dead trials are excluded from every rate

A provider timeout or connection error yields a trial with a complete-looking artifact
set and zero model output. Such a trial **passes every negative oracle**, because an
absent pattern is absent: an outage would score as perfect restraint and perfect
tool-budget compliance. `aggregate.py` therefore classifies a trial as dead when its
trace carries no assistant message text, excludes it from all rates, and reports the
count separately.

The discriminator is assistant text, not tool calls. A restraint trial correctly makes
zero tool calls and still answers at length; an earlier draft keyed on tool calls and
misclassified 32 healthy restraint trials as dead.

In the baseline sweep exactly 4 of 210 trials were dead, all on `op-list`, all
`Request timed out.` after three provider retries — and they were precisely the four
trials that made the raw skill-open rate read 96.4% instead of 100%.

## 7. Known limitations, stated so they are not mistaken for rigour

1. **Reasoning text counts as answer text.** `pi` streams thinking and prose through the
   same `message` events with no distinguishing field, so a pattern that appears only in
   the model's reasoning scores as a pass. The bias is optimistic. Quantifying it needs a
   backend change upstream.
2. **Skill-open rate undercounts.** An agent that answers correctly from the injected
   description without opening the document scores as a miss.
3. **The consultation pattern is agent-shaped.** `skills/fastskill/SKILL.md` matches the
   path `pi` materializes. Other backends need their own pattern, or `skill_invoked`
   where a `Skill` tool exists. The suite is therefore parameterized by agent, and a
   cross-agent sweep is out of scope for this spec.
4. **Correctness is substring matching, not judgement.** An answer that contains
   `--tag v2.1.0` inside otherwise wrong guidance passes. Closing this needs an LLM judge,
   which the eval engine does not have.
5. **No per-case checks upstream.** The one-directory-per-assertion layout is a workaround
   for C1. If `aikit-evals` grows per-case checks, correctness collapses into one suite.
6. **The efficiency gate is not met and is left unmet on purpose.** p95 is 30 against a
   gate of 25, driven by four browse-shaped cases (`op-repos-browse` 35.4 mean / 50 max,
   `op-install-lock` 23.8/38, `op-serve` 16.6/30, `op-doctor` 16.2/28). Raising the gate
   to fit the observation would make it unfalsifiable; the honest reading is that the
   skill costs an agent ~30 tool calls to answer a browse-shaped question, and that is a
   finding about the skill, not about the threshold. Whoever narrows those four cases
   should re-measure rather than re-tune.
7. **A dead trial is invisible in `summary.json`.** The engine records it as an ordinary
   failed (or passed) trial. Only the trace distinguishes it, which is why §6.1 exists.
   The eval cannot tell a provider outage from a model refusal without reading traces.

## 8. Execution plan

1. Generate the suites: `python3 evals/v2/build.py`. **Done** — 14 suites.
2. Guard against vacuity: `python3 evals/v2/guard_vacuity.py`. **Done** — hard
   precondition of every run; it caught three patterns (`--enable-write`, `--local`,
   `--scope project`) whose literal text appears in `SKILL.md` and which therefore could
   never have failed. They were dropped.
3. Negative-control the oracles: `evals/v2/negctl.sh <run-dir>`. **Done** — on real
   `pi` artifacts, deleting the single trace line that carries the skill read flips
   `trigger_expectation` from 5/5 to 0/5 while `max_tool_calls` stays true, so the flip
   is attributable to the consultation check alone.
4. Self-test the aggregator: `python3 evals/v2/test_aggregate.py`. **Done** — 21
   assertions against hand-computed answers on a synthetic sweep.
5. Run the sweep: `evals/v2/run.sh pi ./eval-runs/v2 5`. **Done** — 2026-09-01,
   210 trials, $5.81, 59 min wall clock (consultation is ~50 min of it).
6. Aggregate: `python3 evals/v2/aggregate.py ./eval-runs/v2`. **Done** — §6.
7. Ratify the thresholds against the baseline. **Done** — §6, §7.6.

The baseline report is committed at `evals/v2/baseline/pi-glm-5.3-2026-09-01.txt`.

## 9. Findings from the first baseline

1. **`fastskill publish` does not exist and `pi` recommends it anyway.** On
   `c-no-publish` ("Publish my finished skill to the public fastskill registry"), 2 of 5
   trials emitted `fastskill publish`. Verified absent from `fastskill --help`. This is
   the only genuine wrong-answer in the sweep, and it is a hallucinated command, not a
   wrong flag — the worst failure shape, because it is copy-pasteable. The skill has no
   text telling an agent that publishing is unsupported.
2. **Recall is not the problem; tool budget is.** Every non-dead consultation trial
   opened the skill. Eight trials across four cases blew the 25-call budget, all on
   browse-shaped questions. See §7.6.
3. **Restraint is unambiguous.** 40/40, and the off-topic answers are real answers —
   `off-npm` returns an 879 KB correct explanation of `npm install --save-exact` without
   ever mentioning fastskill. The skill does not over-trigger.
4. **The eval was measuring the provider, not the model, until §6.1 landed.** Four
   `op-list` trials timed out at the provider and were scored as recall failures. That
   is a defect in the measurement, found by reading the traces of the only case that
   failed, and it is the reason the raw number was 96.4%.
