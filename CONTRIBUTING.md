# Contributing to FastSkill Skill

## Repository Structure

```
gofastskill/skill/
├── evals/                        # Eval suite (not packaged in the skill ZIP)
│   ├── prompts.csv               # Eval cases
│   ├── checks.toml               # Deterministic scoring checks
│   ├── fixtures/                 # Recorded runs for offline `eval score` tests
│   └── agent-eval.Dockerfile     # Container for live agent runs
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
fastskill eval score --run-dir evals/fixtures/pass   # must succeed (claude invoked the skill)
fastskill eval score --run-dir evals/fixtures/fail   # must fail (skill never invoked)
```

### Run live (requires an agent CLI + API key)

Runnable agents at the CLI's pinned aikit rev: `codex`, `claude`, `gemini`, `opencode`.
(`pi` and `cursor` are newer aikit agents not yet vendored by fastskill.)

```bash
cd fastskill
fastskill eval run --agent codex --output-dir ../eval-runs
fastskill eval report --run-dir ../eval-runs/<timestamp>
```

Or reproducibly in Docker:

```bash
docker build -f evals/agent-eval.Dockerfile -t fastskill-evals .
docker run --rm -e OPENAI_API_KEY="$OPENAI_API_KEY" fastskill-evals codex
```

Checks are **global** — every check in `checks.toml` is applied to every case — so eval cases
are all positive (`should_trigger = true`); the deterministic model can't express per-case
negative assertions. See `fastskill/references/eval.md` for the prompts/checks schema and
artifact layout.

## CI/CD

`.github/workflows/skill-evals.yml` gates changes to the skill/eval files:

- **validate** and **score-fixtures** run on every push/PR — deterministic, no agent, no tokens.
- **live-eval** is opt-in via *Run workflow* (`workflow_dispatch`), runs the suite against a real
  agent, and needs `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` secrets.

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
