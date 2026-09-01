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

Reported per agent, five trials per case:

| Metric | Definition | CI gate (after baseline) |
|---|---|---|
| Skill-open rate | passing consultation trials / total | ≥ 0.85 |
| Restraint rate | passing restraint trials / total | ≥ 0.90 |
| Answer accuracy | passing correctness trials / total | ≥ 0.80 |
| Efficiency | p95 tool calls per consultation case | ≤ 25 |
| Cost | USD per full sweep | reported, not gated |

Thresholds are proposals to be ratified against the first baseline, not asserted in
advance. Gating before a baseline exists is how a suite gets disabled.

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

## 8. Execution plan

1. Author `patterns.json`, the suites, the guard, and the runner.
2. Run the guard. It must report zero vacuous patterns before any agent runs.
3. Negative-control the oracles: confirm the consultation pattern is absent from a
   restraint trace and present in a consultation trace, on real artifacts.
4. Run the full sweep against `pi` with five trials, `--no-fail`.
5. Aggregate and report the four metrics with per-case detail.
6. Ratify thresholds, then wire the gate.
