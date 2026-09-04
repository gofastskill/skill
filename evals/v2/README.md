# Enhanced eval suite (spec 001)

Measures how well the fastskill skill actually performs, rather than whether it smoke-tests.
Read [`specs/001-enhanced-eval.md`](../../specs/001-enhanced-eval.md) for the design and the
engine constraints it works around.

## What it measures

| Suite | Question | How it is checked |
|---|---|---|
| `consultation/` | Is the skill opened when it should be? | `should_trigger = true` on every case, which generates a `skill_invoked` check |
| `restraint/` | Is it left alone when it should be? | `should_trigger = false`, generating the same check with inverted polarity |
| `correctness/` | Is the answer right? | one `command_contains` per case, scoped to it, on a scenario-unique flag and value — plus a judge, scored against a reference answer |

## Layout

Everything is generated from `patterns.json` except `correctness/judge-prompt.md`, which is
prose and is written by hand. Do not hand-edit the generated files — `build.py` overwrites
them, and CI regenerates and diffs to prove it was not tried.

```bash
python3 evals/v2/build.py          # regenerate suites from patterns.json
python3 evals/v2/guard_vacuity.py  # prove no check can pass on a mere read

export AIKIT_LLM_URL=https://…/v1  # the judge's endpoint — there is no default
export JUDGE_API_KEY=…             # its key, named by api_key_env in checks.toml
export JUDGE_MODEL=glm-5.3         # optional; overrides the model checks.toml declares
./evals/v2/run.sh pi ./eval-runs/v2 5
```

`run.sh` checks those two variables before the first suite runs rather than when it reaches
the judged one, because correctness is last: a key missing at its turn would surface only
after the other two suites had been paid for in full.

`run.sh` ends by folding every run into the metrics in `metrics.toml`, so there is no
separate aggregation step. To re-fold an existing sweep without re-running it:

```bash
fastskill eval scorecard --root ./eval-runs/v2 --metrics evals/v2/metrics.toml
```

## Three suites, not fourteen

Correctness used to be twelve single-case suites. A suite's checks applied to all of its
cases and there was no way to say otherwise, so two cases needing different assertions could
not share one. `[[check]]` entries now take a `cases` list, and the twelve collapse into one
suite whose checks are each scoped to the case they belong to.

Skill invocation is no longer written into any `checks.toml`. The `should_trigger` column
generates it. That column used to be parsed and read by nothing, so a case marked `false`
asserted nothing at all while every reader of the CSV assumed otherwise. `restraint/`'s
checks file is now a header and nothing else, and it is still fully scored.

Correctness cases are on-topic, so they keep `should_trigger = true` and gain the generated
check too. That is a second, independent assertion rather than a dilution of the first: the
scorecard keeps a rate per check type, so consulting the skill and answering correctly are
reported as the separate things they are.

## The judge

`correctness/checks.toml` declares one `[[judge]]`, `command-correctness`. It reads the
agent's answer beside a reference answer and scores three criteria: `right_command` (a 1–5
scale), `would_run` and `no_unrequested_side_effects` (both boolean). Its prompt is the one
hand-written file in the suite, `correctness/judge-prompt.md`; everything else about it —
name, criteria, defaults — comes from `patterns.json` like the rest.

### Why, when there is already a check per case

A substring check sees the substring it was given and nothing around it. Case
`c-marketplace-baseurl` requires `--base-url https://cdn.acme.io/skills/`, and this answer
contains it:

```
fastskill marketplace create --path ./team-skills --base-url https://cdn.acme.io/skills/
```

That command does not run. `--path` is not a fastskill argument — the directory is
positional — so the binary rejects it before doing anything, and the check passes anyway.
`would_run` is the criterion that asks the question the substring cannot, which is why
`metrics.toml` breaks it out on its own.

### The reference answer

The `expected` column of `prompts.csv` carries one correct response per case, rendered into
the judge prompt as `{{case.expected}}`. It reaches the judge and nothing else: the runner
sends the agent `case.prompt` alone, no check reads the column, and `guard_vacuity.py`
deliberately does not scan it — a reference answer is not a pattern that could be satisfied
by a read.

### Advisory, for now

The judge declares no `min_score`, so it scores without moving any verdict, and both
`judge_score` metrics carry `min_score = 0.0`, so they report without gating. A bar set
before there are judgments to set it from would be a number nobody measured. Ratify one
against the first judged sweep instead.

### The model is a placeholder

`[judge_defaults] model` is committed as `gpt-4.1` and has to exist on whatever
`AIKIT_LLM_URL` serves; `JUDGE_MODEL` (`--judge-model`) overrides it. The committed file
names no endpoint on purpose — a judge with a default endpoint is a judge that quietly calls
someone. `eval validate` warns when the judge's model is the model under test, because a
model grading itself is a weak witness.

## The vacuity guard is not optional

Text checks substring-match the whole trace, and the trace contains every file the agent
read — including `SKILL.md` itself. A pattern that occurs in the skill document therefore
matches as soon as the agent opens it, whatever it answered. `guard_vacuity.py` proves no
pattern in `patterns.json` occurs anywhere in the skill payload. It caught three such
patterns (`--enable-write`, `--local`, `--scope project`) during authoring. Run it before
trusting any number this suite produces.

This is why positive patterns pair a flag with a value invented for the prompt: `--tag` is
vacuous, `--tag v2.1.0` is not.

Only the text patterns need the guard. Skill invocation is checked against decoded tool-use
frames rather than trace text, so no string in the payload can satisfy it.

## The checks are themselves tested

Three layers, because a broken measurement is worse than no measurement:

| Script | What it proves | When it runs |
|---|---|---|
| `guard_vacuity.py` | no pattern occurs in the skill payload, so no check passes on a mere read | hard precondition of every `run.sh` |
| `negctl.sh` | the consultation check *fails* when the skill read is deleted from a real trace | after a sweep, against real artifacts |
| `stage.sh` + `eval validate` | every suite parses, and the judge's prompt uses the variables the engine requires | the `validate-v2` CI job, every pull request |

```bash
evals/v2/negctl.sh ./eval-runs/v2/consultation/<timestamp>/pi
```

`negctl.sh` copies one real completed case twice, strips every trace line naming the staged
skill path from one copy, and re-scores both with `fastskill eval score`. Measured on the
first pi sweep, when the check was still a text expectation:

```
  present  passed 1.00 [('trigger_expectation', True),  ('max_tool_calls', True)]
  absent   failed 0.00 [('trigger_expectation', False), ('max_tool_calls', True)]
```

Exactly one trace line per trial carries the read, and `max_tool_calls` is unmoved, so the
flip is attributable to the consultation check alone. The check is now `skill_invoked` and
the control reads the path it matches out of each trial's `result.json`, so it deletes the
evidence the check reads rather than a string that resembles it.

## Agent support

Skill invocation counts two shapes: a tool use named `Skill`, which only Claude Code emits,
and **any** tool use whose input references the skill document's path. `pi` has no `Skill`
tool — it loads skills via `--no-skills --skill <path>` and exposes only `read`, `bash`,
`edit`, `write` — so a skill read arrives there as a `read` call with the path in its
arguments. Both shapes satisfy the same check, so both agents run in one sweep with no
agent-keyed configuration.

Backends whose decoder emits no tool-use frames at all (`gemini`, `opencode`, `cursor`)
cannot produce the evidence these suites need. `eval validate` and `eval run` refuse the
combination up front rather than spending tokens on trials that could not be scored.

## What the numbers exclude

Two exclusions are applied by the tool, and neither is configurable here:

- **Trials with outcome `error`.** A trial that produced no measurement still carries check
  results, because the checks ran over an empty trace — where every negative expectation and
  every tool-call ceiling passes vacuously. Counting them would report an outage as a clean
  sweep. The scorecard reports the count separately.
- **Check results marked not observable.** They record `passed: false` so that older readers
  stay conservative, and are counted as neither a pass nor a failure by anything that
  understands the field.

Cost is summed from the vendor-reported figure only, and reads "not reported" when the
backend supplied none. It is never estimated from a local price table: a stale estimate is
indistinguishable from a real number once it reaches a report.
