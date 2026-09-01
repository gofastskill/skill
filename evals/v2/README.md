# Enhanced eval suite (spec 001)

Measures how well the fastskill skill actually performs, rather than whether it smoke-tests.
Read [`specs/001-enhanced-eval.md`](../../specs/001-enhanced-eval.md) for the design and the
engine constraints it works around.

## What it measures

| Suite | Question | Oracle |
|---|---|---|
| `consultation/` | Is the skill opened when it should be? | the materialized skill path appears in a `read` tool call |
| `restraint/` | Is it left alone when it should be? | the same path is **absent** |
| `correctness/<id>/` | Is the answer right? | a scenario-unique flag+value the agent can only have synthesized |

## Layout

Everything is generated from `patterns.json`. Do not hand-edit the suites.

```bash
python3 evals/v2/build.py          # regenerate suites from patterns.json
python3 evals/v2/guard_vacuity.py  # prove no oracle can pass vacuously
./evals/v2/run.sh pi ./eval-runs/v2 5
python3 evals/v2/aggregate.py ./eval-runs/v2
```

## The vacuity guard is not optional

Text checks substring-match the whole trace, and the trace contains every file the agent
read — including `SKILL.md` itself. A pattern that occurs in the skill document therefore
matches as soon as the agent opens it, whatever it answered. `guard_vacuity.py` proves no
pattern in `patterns.json` occurs anywhere in the skill payload. It caught three such
patterns (`--enable-write`, `--local`, `--scope project`) during authoring. Run it before
trusting any number this suite produces.

This is why positive patterns pair a flag with a value invented for the prompt: `--tag` is
vacuous, `--tag v2.1.0` is not.

## The oracles are themselves tested

Three layers, because a broken measurement is worse than no measurement:

| Script | What it proves | When it runs |
|---|---|---|
| `guard_vacuity.py` | no pattern occurs in the skill payload, so no oracle passes on a mere read | hard precondition of every `run.sh` |
| `negctl.sh` | the consultation oracle *fails* when the skill read is deleted from a real trace | after a sweep, against real artifacts |
| `test_aggregate.py` | the four metrics match hand-computed answers on a synthetic sweep | any time, no agent needed |

```bash
python3 evals/v2/test_aggregate.py
evals/v2/negctl.sh ./eval-runs/v2/consultation/<timestamp>/pi
```

`negctl.sh` copies one real completed case twice, strips every trace line naming the
skill path from one copy, and re-scores both with `fastskill eval score`. Measured on
the first pi sweep:

```
  present  passed 1.00 [('trigger_expectation', True),  ('max_tool_calls', True)]
  absent   failed 0.00 [('trigger_expectation', False), ('max_tool_calls', True)]
```

Exactly one trace line per trial carries the read, and `max_tool_calls` is unmoved, so
the flip is attributable to the consultation check alone.

## Agent support

The oracle is the skill path in a `read` call because `pi` has no `Skill` tool — it loads
skills via `--no-skills --skill <path>` and exposes only `read`, `bash`, `edit`, `write`.
Agents that *do* expose a `Skill` tool (Claude Code) should use the `skill_invoked` check
instead; `patterns.json` would need an agent-keyed oracle to run both in one sweep. Out of
scope for spec 001, which measures `pi`.
