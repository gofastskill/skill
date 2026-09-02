# Contributing to FastSkill Skill

## Repository Structure

```
gofastskill/skill/
├── evals/                        # Eval suites (not packaged in the skill ZIP)
│   ├── README.md                 # How to run both suites, and the methodology
│   ├── prompts.csv               # v1 eval cases
│   ├── checks.toml               # v1 deterministic scoring checks
│   ├── fixtures/                 # Recorded runs for offline `eval score` tests
│   ├── agent-eval.Dockerfile     # Container for live agent runs
│   └── v2/                       # Enhanced suite (specs/001) — recall, restraint, correctness
├── specs/                        # Design records for non-obvious changes
└── fastskill/                    # Shippable skill
    ├── SKILL.md                  # Skill documentation
    ├── skill-project.toml        # Metadata + [tool.fastskill.eval] → ../evals/*
    └── references/               # eval.md and other reference material
```

There is a single `skill-project.toml` (inside `fastskill/`). Run FastSkill commands
from the `fastskill/` directory so path resolution finds that manifest and `../evals/`.

## Development

1. Edit files in the `fastskill/` subdirectory (and `evals/` when extending the suite)
2. Open a pull request from a branch off the latest `origin/main` (see `CLAUDE.md`) —
   changes land via PR with required status checks, not by pushing to `main` directly
3. On merge, the CI/CD workflow automatically packages and publishes a new release

## Evaluations

The skill ships an eval suite so its trigger behavior and guidance stay correct. Config lives
in `[tool.fastskill.eval]` in `fastskill/skill-project.toml` and points at `../evals/`.

The commands below cover the default (v1) suite, which is what CI gates. There is a second,
larger suite under `evals/v2/` that measures recall, restraint and answer correctness across
five trials per case; it runs on demand rather than in CI. **[`evals/README.md`](evals/README.md)
covers both suites and the methodology** — read it before adding or changing an eval case.

### Validate (deterministic, no agent)

```bash
cd fastskill
fastskill eval validate          # checks prompts.csv, checks.toml, and config schema
fastskill eval validate --json
```

### Score fixtures (deterministic, no agent)

`evals/fixtures/` holds recorded runs. `eval score` re-applies `checks.toml` to them offline,
which is how CI exercises the checks engine without spending tokens:

```bash
# run from the repository root: the recorded summary.json points at evals/checks.toml
# relative to the current directory, which is also how CI invokes it
fastskill eval score --run-dir evals/fixtures/pass   # must succeed (claude invoked the skill)
fastskill eval score --run-dir evals/fixtures/fail   # must fail (skill never invoked)
```

### Run live (requires an agent CLI + API key)

Agent keys the CLI knows: `aikit`, `claude`, `codex`, `cursor`, `gemini`, `pi`
(`fastskill eval validate --all` lists which of them are installed on your machine).

```bash
cd fastskill
fastskill eval run --agent codex --output-dir ../eval-runs
fastskill eval report --run-dir ../eval-runs/<timestamp>/codex   # the per-agent directory
```

Or reproducibly in Docker:

```bash
docker build -f evals/agent-eval.Dockerfile -t fastskill-evals .
docker run --rm -e OPENAI_API_KEY="$OPENAI_API_KEY" fastskill-evals codex
```

Checks are **global** — every check in `checks.toml` is applied to every case — so v1's cases
are all positive (`should_trigger = true`). Note that `should_trigger` is documentation only:
it is parsed into the case and never read by a check, so it asserts nothing by itself. A
negative expectation has to be written as a check with `expected = false`, and because checks
are global that means a separate suite — which is how `evals/v2/` expresses per-case
assertions. See `fastskill/references/eval.md` for the prompts/checks schema and artifact
layout.

## CI/CD

`.github/workflows/skill-evals.yml` gates changes to the skill/eval files:

- **validate** and **score-fixtures** run on every push/PR — deterministic, no agent, no tokens.
- **live-eval** is opt-in via *Run workflow* (`workflow_dispatch`), runs the v1 suite against a
  real agent, and needs `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` secrets.

No CI job runs `evals/v2/` — at roughly $6 and an hour per sweep it belongs on a schedule or a
manual trigger, and nothing enforces its thresholds yet.

`.github/workflows/publish-skill.yml`:

- Detects changes to `fastskill/` directory
- Packages skill using FastSkill CLI
- Creates a GitHub release with the packaged skill artifact
- Uses GitHub App token for release operations

## Required Secrets

The workflow requires the following repository secrets:

- `GH_APP_ID`: GitHub App ID for token generation
- `GH_APP_PRIVATE_KEY`: GitHub App private key for authentication
- `GITHUB_TOKEN`: Repository access token (automatically provided by GitHub Actions)
