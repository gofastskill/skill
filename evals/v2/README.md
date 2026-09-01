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

## Agent support

The oracle is the skill path in a `read` call because `pi` has no `Skill` tool — it loads
skills via `--no-skills --skill <path>` and exposes only `read`, `bash`, `edit`, `write`.
Agents that *do* expose a `Skill` tool (Claude Code) should use the `skill_invoked` check
instead; `patterns.json` would need an agent-keyed oracle to run both in one sweep. Out of
scope for spec 001, which measures `pi`.
