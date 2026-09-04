---
name: fastskill
version: 1.1.0
description: Package manager and operational toolkit for Claude Code-compatible skills. Use this skill when installing, managing, discovering, or analyzing skills; configuring repositories; running skill evaluations (`fastskill eval`) or the optimization loop (`fastskill optimize`); serving skills over HTTP/MCP; or building marketplace catalogs. See references/eval.md for eval setup in full.
license: Apache-2.0
---

# FastSkill

FastSkill is a package manager and operational toolkit for Claude Code-compatible skills. It provides discovery, installation, versioning, semantic search, quality evals, and a local HTTP/MCP server for skills at scale.

## Overview

FastSkill follows Anthropic's standardized `SKILL.md` skill layout and adds a manifest (`skill-project.toml`), a lockfile (`skills.lock`), semantic search, evaluation suites, an optimization loop, and repository/marketplace tooling. Modern agents (Claude Code, Cursor, …) read installed skills directly from the skills directory — **there is no metadata-file sync step**.

## Installation

```bash
# Quick install (recommended)
curl -fsSL https://raw.githubusercontent.com/gofastskill/fastskill/main/scripts/install.sh | bash

# Or via Homebrew (macOS & Linux)
brew install gofastskill/cli/fastskill

# Or via Scoop (Windows)
scoop bucket add gofastskill https://github.com/gofastskill/scoop-bucket
scoop install fastskill

# Or via Cargo
cargo install fastskill
```

Verify:

```bash
fastskill --version
```

## Configuration

FastSkill uses **`skill-project.toml`** as the single configuration file for both project-level and skill-level contexts. FastSkill walks up the directory tree from the current directory to find it.

### Quick setup

```bash
fastskill init
```

This creates a `skill-project.toml` with the standard sections.

### Minimal configuration (enables reindex / search)

Semantic search is the only feature that needs the embedding section. Everything else works without it.

```toml
# skill-project.toml  (minimum for reindex + search)
[tool.fastskill.embedding]
openai_base_url = "https://api.openai.com/v1"
embedding_model = "text-embedding-3-small"
```

Required environment variable for embeddings: **`OPENAI_API_KEY`**. `skills_directory` is not required for `reindex`/`search` if skills are already installed under the default `.claude/skills/` path.

### Configuration file structure

```toml
[metadata]
id = "my-skill"
version = "1.0.0"

[dependencies]
# Add your skill dependencies here

[tool.fastskill]
skills_directory = ".claude/skills"

[tool.fastskill.embedding]
openai_base_url = "https://api.openai.com/v1"
embedding_model = "text-embedding-3-small"

[[tool.fastskill.repositories]]
name = "anthropic"
type = "git-marketplace"
url = "https://github.com/anthropics/skills"
priority = 0
```

### Full schema reference

```
skill-project.toml
├── [metadata]              — skill identity (required when authoring/publishing a skill)
│     id                   — string, unique skill ID (no slashes; scope is a separate concept)
│     version              — semver string
│     name                 — human-readable name
│     description          — one-line description
│     author               — optional
│     compatibility        — optional, Claude version constraint
│     download_url         — optional
│     tags / capabilities  — optional string arrays
├── [dependencies]          — skill dependencies (optional, may be empty table)
├── [tool.fastskill]        — fastskill runtime config (optional section)
│     skills_directory      — path where installed skills are stored (default: .claude/skills/)
│     install_depth         — max transitive dependency depth (default: 5)
│     skip_transitive       — skip transitive deps (default: false)
│     auto_reindex          — reindex automatically after add/install/update/remove (default: true)
├── [tool.fastskill.embedding]  — required only for reindex / search
│     openai_base_url       — REQUIRED string, OpenAI-compatible API base URL
│     embedding_model       — REQUIRED string, model name
│     index_path            — optional path, default: .claude/.fastskill/index.db
├── [tool.fastskill.eval]   — skill evaluation config (see references/eval.md)
│     prompts / checks / timeout_seconds / fail_on_missing_agent
├── [tool.fastskill.server] — serve CORS config: allowed_origins, allowed_headers
└── [[tool.fastskill.repositories]]  — zero or more repository entries
      name                  — REQUIRED string, unique repo label
      type                  — REQUIRED enum: git-marketplace | http-registry | zip-url | local
      REQUIRED source-type-specific location — exactly one, matching `type`:
        git-marketplace → url        http-registry → index_url
        zip-url         → zip_url    local         → path
      branch                — optional, git branch (git-marketplace only)
      priority              — REQUIRED integer, lower = higher priority
      auth                  — optional table: { type = "pat", env_var = "VAR" }
                              **http-registry only** — other source types
                              authenticate differently and ignore or reject it.
                              See "Authentication" below.
```

Configuration is stored **only** in `skill-project.toml`. FastSkill does not read a separate `.fastskill/config.yaml` file.

### Environment variables

```bash
export OPENAI_API_KEY="your-key-here"        # embeddings / semantic search
export FASTSKILL_API_URL="https://registry.example.com"   # default registry target
```

Additional: `REGISTRY_INDEX_PATH` (override index path), `FASTSKILL_NO_PROGRESS` (disable progress bars), `FASTSKILL_AUTH_TOKEN` / `FASTSKILL_TOKEN` (registry auth token, checked by `doctor`). Repository PAT auth reads a per-repo `env_var` (default `PAT_TOKEN`).

## Skill evaluations (evals)

The CLI runs **skill evaluations**: prompts from a CSV, optional deterministic **checks** (TOML), agent execution via aikit-sdk, and timestamped artifact directories. Configuration lives in `[tool.fastskill.eval]` inside `skill-project.toml`. Cases run **isolated by default** — a per-case scratch workspace containing only the skill under test (needs `SKILL.md` + `[metadata].id`; opt out with `--no-isolation`) — so trigger rates measure the skill, not the machine.

**You MUST** follow the dedicated guide for CSV and checks schema, CLI commands (`eval validate`, `eval run`, `eval report`, `eval score`), pass/fail rules, and packaging notes:

- **[Skill evals guide](references/eval.md)** — setup, prompts CSV, `checks.toml`, agents, artifacts, CI.

## Basic usage

### Adding skills

```bash
# From git repository
fastskill add https://github.com/org/skill.git

# From a git repository subdirectory (GitHub tree URL: tree/<branch>/<path/to/skill>)
fastskill add "https://github.com/org/repo/tree/main/path/to/skill"

# From a local folder
fastskill add ./local-skill

# Editable mode (symlink a local folder for development)
fastskill add ./local-skill -e

# Every skill under a local folder (recursive)
fastskill add ./skills -r

# From a registry with version
fastskill add scope/pptx@1.0.0

# From git with branch/tag
fastskill add https://github.com/org/skill.git --branch main
fastskill add https://github.com/org/skill.git --tag v1.0.0

# Add to a group
fastskill add https://github.com/org/skill.git --group dev
```

### Installing from the manifest

Declare dependencies in `skill-project.toml`:

```toml
[dependencies]
web-scraper = { origin = { type = "git", url = "https://github.com/org/web-scraper.git" } }
data-processor = { origin = { type = "git", url = "https://github.com/org/data-processor.git" }, groups = ["prod"] }
```

Pin a branch, tag, or commit with `ref`:

```toml
web-scraper = { origin = { type = "git", url = "https://github.com/org/web-scraper.git", ref = { branch = "main" } } }
```

> The older `{ source = "git", url = ... }` shape (no `origin` wrapper) still reads and is
> silently upgraded in memory, but it's slated for removal — write new manifests with
> `origin`.

Install:

```bash
fastskill install                 # apply the manifest, update skills.lock
fastskill install --lock          # install exact versions from skills.lock (reproducible)
fastskill install --only prod     # only the prod group
fastskill install --without dev   # everything except the dev group
```

### Listing, reading, and removing skills

```bash
fastskill list                    # list installed skills with reconciliation status
fastskill list --json             # machine-readable
fastskill read my-skill-id        # print the skill's SKILL.md
fastskill read my-skill-id --meta # metadata only
fastskill read my-skill-id --tree # dependency tree
fastskill remove my-skill-id      # uninstall and update manifest + lock
```

`fastskill <skill-id>` is shorthand for `fastskill read <skill-id>`.

### Updating skills

```bash
fastskill update                  # update all skills from their recorded source
fastskill update my-skill-id      # update one skill
fastskill update --check          # report what would change without writing
fastskill update --dry-run        # preview
```

### Semantic search

```bash
fastskill reindex                 # build/refresh the local vector index
fastskill reindex --force         # force a full re-index

fastskill search "powerpoint presentation"        # remote catalogs (default)
fastskill search "data processing" --local        # installed skills
fastskill search "charts" --local --limit 5 --format json
```

Search needs an embedding provider (`[tool.fastskill.embedding]` + `OPENAI_API_KEY`) for semantic ranking; without it, local search falls back to keyword matching. Add/install/update/remove auto-reindex when `auto_reindex = true` (skipped silently if no embedding provider is configured); use `--no-reindex` to opt out.

## Repository management

FastSkill manages skill sources through the `repos` command group. Repositories are stored in `[[tool.fastskill.repositories]]` in `skill-project.toml`.

```bash
# Add repositories (type: git-marketplace | http-registry | zip-url | local)
fastskill repos add team-skills --repo-type git-marketplace https://github.com/org/team-skills.git
fastskill repos add prod-registry --repo-type http-registry https://api.fastskill.io/index
fastskill repos add official --repo-type zip-url https://example.com/skills/
fastskill repos add local-dev --repo-type local ./local-skills

# Inspect and maintain
fastskill repos list                          # list configured repositories
fastskill repos info team-skills              # repository details
fastskill repos test team-skills              # connectivity check
fastskill repos update team-skills --branch main --priority 1
fastskill repos refresh                       # refresh cached catalog metadata
fastskill repos remove team-skills

# Browse catalogs
fastskill repos skills --repository prod-registry [--scope engineering] [--all-versions]
fastskill repos show engineering/data-analyzer --repository prod-registry
fastskill repos versions engineering/data-analyzer --repository prod-registry
```

Search across configured registries with `fastskill search "<query>" --repository <name>`.

**git-marketplace requirements**: the repository must contain a `marketplace.json` at `.claude-plugin/marketplace.json` (Claude Code standard) or `marketplace.json` (root, legacy).

**Authentication** uses env-var indirection — never store plaintext tokens:

```toml
[[tool.fastskill.repositories]]
name = "production-registry"
type = "http-registry"
index_url = "https://api.fastskill.io/index"
auth = { type = "pat", env_var = "FASTSKILL_TOKEN" }
```

The `auth` block applies to **`http-registry` sources only**. Every other source type
authenticates by a different mechanism, and `auth` is not consulted for them:

| Source type | How to authenticate |
|---|---|
| `http-registry` | `auth = { type = "pat", env_var = "..." }` (above). |
| `git-marketplace` | The system git credential helper (`gh auth login`, `git config credential.helper`) or an SSH remote plus a key in your SSH agent. FastSkill shells out to `git` and never injects PATs — setting `auth` here is rejected with an error. |
| `zip-url` | A **pre-signed URL** (S3/GCS), which carries the credential in the URL itself. A zip-url fetch is a plain HTTP GET that sends no auth headers. |
| `local` | Filesystem permissions. |

> Do not rely on `auth` to protect a private `zip-url` artifact — it is not applied to
> the request. Use a pre-signed URL instead.

## Building marketplace catalogs

Generate a `marketplace.json` from a folder of skills so others can consume them as a `git-marketplace` repository.

```bash
fastskill marketplace create ./skills --name "My Marketplace"
fastskill marketplace create . -o .claude-plugin/marketplace.json --name "My Marketplace" --base-url https://example.com/skills/
```

The directory to scan is a **positional argument**, not an option — there is no `--path`.

| Argument / Option | Description |
|--------|-------------|
| `<PATH>` | Positional. Root to scan for skills (default `.`) |
| `-o, --output <FILE>` | Output path (default `.claude-plugin/marketplace.json`) |
| `--name <NAME>` | **Required.** Marketplace name |
| `--base-url <URL>` | Base URL for download links |
| `--skills-dir <DIR>` | Override the skills directory path |
| `--owner-name` / `--owner-email` / `--description` / `--repo-version` | Optional metadata |

> The metadata version flag is `--repo-version`. `--version` is the CLI's own version flag:
> passing it prints the FastSkill version and exits without creating anything.

> **Distribution note:** the `fastskill` CLI does not include `publish`/`auth`/`package` commands. Skill distribution to a hosted registry is handled by the platform operator (a managed deploy workflow), not a self-hosted CLI publish path. Author locally, share via git/zip/marketplace catalogs, or hand artifacts to your registry operator.

## Analyzing a skill collection

`analyze` uses the semantic index to find overlap across skills (requires an embedding provider and an index — run `reindex` first).

```bash
fastskill analyze matrix --threshold 0.8        # pairwise similarity
fastskill analyze cluster -k 8 --min-size 2     # semantic clusters
fastskill analyze duplicates --threshold 0.92 --severity high   # near-duplicates
```

## Optimizing skills

`optimize` runs an automated text-gradient loop that improves a skill document against eval cases: propose a patch → run the target agent → grade → accept if the score improves → repeat, writing the best version to disk.

```bash
fastskill optimize run --config optimize.toml --out-dir ./optimize-runs
fastskill optimize status ./optimize-runs/<run> [--watch]
fastskill optimize resume ./optimize-runs/<run>
fastskill optimize inspect ./optimize-runs/<run> --step 3 --show all
fastskill optimize export ./optimize-runs/<run> --out ./best_skill.md
```

Scoring passes (rollouts, gate, baseline, final) are **isolated by default**: each case scores in a scratch workspace containing only the candidate skill. Set `isolate = false` in the config or pass `optimize run --no-isolation` to score against the machine's ambient environment instead; the decision is persisted into the run's provenance config so `resume` replays it. Baselines recorded before isolation existed will shift on the first isolated run.

## Serving skills (HTTP API and MCP)

Start a local server exposing an HTTP API and web UI:

```bash
fastskill serve                                 # read-only by default
fastskill serve --host 0.0.0.0 --port 8080
fastskill serve --enable-write                  # enable state-changing endpoints
```

The server is **read-only by default** (ADR-0003): read endpoints (list/get skills, project, search, resolve, status, registry browse, dashboard) are always available; every write endpoint (install/update/remove/reindex/manifest edits) returns **HTTP 403** unless you start the server with `--enable-write`. `serve` enforces **no authentication of its own** — run it local-first, or place an authenticating reverse proxy in front if you expose it.

All application routes are versioned under **`/api/v1/…`** (requests to `/api/…` redirect 308 to `/api/v1/…`).

| Endpoint | Method | Access | Description |
|----------|--------|--------|-------------|
| `/api/v1/skills` | GET | read | List installed skills |
| `/api/v1/skills/{id}` | GET | read | Get a skill |
| `/api/v1/skills/{id}/content` | GET | read | Get `SKILL.md` content |
| `/api/v1/project` | GET | read | Project manifest view |
| `/api/v1/search` | POST | read | Search skills (`{"query":"…","limit":N}`) |
| `/api/v1/resolve` | POST | read | Resolve the most relevant skills for a prompt |
| `/api/v1/status` | GET | read | Service status + capability flags |
| `/api/v1/registry/*` | GET | read | Browse registry sources / index / versions |
| `/api/v1/skills/install` | POST | **write** | Install a skill from an origin |
| `/api/v1/skills/update` | POST | **write** | Update one or all skills |
| `/api/v1/skills/{id}` | DELETE | **write** | Remove a skill |
| `/api/v1/reindex` | POST | **write** | Reindex |
| `/api/v1/registry/refresh` | POST | **write** | Refresh registry sources |
| `/api/v1/manifest/skills` | POST/PUT/DELETE | **write** | Manifest skill management |
| `/healthz`, `/readyz` | GET | read | Liveness / readiness probes |

### MCP server (expose FastSkill to your agent)

```bash
# Run an MCP server that exposes every CLI command as a tool `fastskill.<path>`
fastskill mcp serve --transport stdio
fastskill mcp serve --transport http --port 8080 --path /mcp

# Write MCP server config into an agent's config
fastskill mcp install --agent claude --scope project --stdio
fastskill mcp list
```

`mcp install` supports agents `claude`, `cursor`, `gemini`, `copilot`, `opencode`, and `codex`, at `--scope project` or `global`.

## Diagnostics

```bash
fastskill doctor          # check skills dir, skill-project.toml, embedding config, OPENAI_API_KEY, auth token
fastskill doctor --json
```

Add `-v` / `--verbose` to any command for more detail.

## CI/CD integration

### GitHub Actions

```yaml
name: Skills CI

on:
  push:
    branches: [main]
    paths: ['skills/**', 'skill-project.toml', 'skills.lock']

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install FastSkill
        run: curl -fsSL https://raw.githubusercontent.com/gofastskill/fastskill/main/scripts/install.sh | bash

      - name: Reproducible install
        run: fastskill install --lock

      - name: Validate evals
        run: fastskill eval validate
```

Set `OPENAI_API_KEY` and any repository PAT env vars as CI secrets when your workflow uses search or private repositories.

## Troubleshooting

### "Embedding configuration required but not found"

1. Run `fastskill init` (or add `[tool.fastskill.embedding]` to `skill-project.toml`).
2. Set `OPENAI_API_KEY`.
3. Re-run `fastskill reindex`.

### Repository source not appearing

- Verify `marketplace.json` exists at the expected location for `git-marketplace`.
- Confirm the repo `type` and URL are correct; run `fastskill repos test <name>`.

### Search returns nothing

- Run `fastskill reindex` to (re)build the index.
- Confirm `OPENAI_API_KEY` and `[tool.fastskill.embedding]` are set (`fastskill doctor`).

## Version management

FastSkill uses semantic versioning. A skill's version is read from the `[metadata]` section of its `skill-project.toml`.

## Additional resources

- **[Skill evals (`fastskill eval`)](references/eval.md)** — eval config, prompts CSV, checks TOML, running/scoring, artifacts.
- Full documentation: <https://docs.gofastskill.com/>
