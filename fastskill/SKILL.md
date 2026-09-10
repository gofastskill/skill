---
name: fastskill
version: 2.0.0
description: Package manager and operational toolkit for Claude Code-compatible skills. Use this skill when installing, managing, discovering, bundling, or analyzing skills; configuring repositories; running skill evaluations (`fastskill eval validate/run/judge/report/score/scorecard`) or the optimization loop (`fastskill optimization`); serving skills over HTTP/MCP; or building marketplace catalogs. See references/eval.md for eval setup in full.
license: Apache-2.0
---

# FastSkill

FastSkill is a package manager and operational toolkit for Claude Code-compatible skills. It provides discovery, installation, versioning, self-contained team bundles, semantic search, quality evals, and a local HTTP/MCP server for skills at scale.

## Overview

FastSkill follows Anthropic's standardized `SKILL.md` skill layout and adds a manifest (`skill-project.toml`), a lockfile (`skills.lock`), self-contained bundles, semantic search, evaluation suites, an optimization loop, and repository/marketplace tooling. Modern agents (Claude Code, Cursor, …) read installed skills directly from the skills directory — **there is no metadata-file sync step**.

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
fastskill project init
```

This creates a `skill-project.toml` with the standard sections.

### Minimal configuration (enables index rebuild / skill search)

Semantic search is the only feature that needs the embedding section. Everything else works without it.

```toml
# skill-project.toml  (minimum for index rebuild + skill search)
schema_version = "1"

[dependencies]

[tool.fastskill]
skills_directory = ".claude/skills"

[tool.fastskill.embedding]
openai_base_url = "https://api.openai.com/v1"
embedding_model = "text-embedding-3-small"
```

Required environment variable for embeddings: **`OPENAI_API_KEY`**. Local search falls back to
keyword matching when embeddings are not configured.

### Configuration file structure

```toml
schema_version = "1"

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
├── schema_version = "1"    — current on-disk manifest schema; write this in new manifests
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
│     auto_reindex          — rebuild the index after package state changes (default: true)
├── [tool.fastskill.embedding]  — required only for index rebuild / skill search
│     openai_base_url       — REQUIRED string, OpenAI-compatible API base URL
│     embedding_model       — REQUIRED string, model name
│     index_path            — optional path, default: .claude/.fastskill/index.db
├── [tool.fastskill.eval]   — skill evaluation config (see references/eval.md)
│     prompts / checks / timeout_seconds / fail_on_missing_agent
├── [tool.fastskill.server] — server CORS config: allowed_origins, allowed_headers
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
```

Additional: `REGISTRY_INDEX_PATH` overrides the local index path and `FASTSKILL_NO_PROGRESS`
disables index progress bars. `cli doctor` recognizes `FASTSKILL_AUTH_TOKEN` or `FASTSKILL_TOKEN`;
repository authentication reads the `env_var` configured on that repository (default
`PAT_TOKEN`).

## Skill evaluations (evals)

The CLI runs **skill evaluations**: prompts from a CSV, optional deterministic **checks** (TOML), agent execution via aikit-sdk, and timestamped artifact directories. Configuration lives in `[tool.fastskill.eval]` inside `skill-project.toml`. Cases run **isolated by default** — a per-case scratch workspace containing only the skill under test (needs `SKILL.md` + `[metadata].id`; opt out with `--no-isolation`) — so trigger rates measure the skill, not the machine.

**You MUST** follow the dedicated guide for CSV, checks, judges, scorecards, CLI commands
(`eval validate`, `eval run`, `eval judge`, `eval report`, `eval score`, `eval scorecard`), and
pass/fail rules:

- **[Skill evals guide](references/eval.md)** — setup, prompts CSV, `checks.toml`, agents, artifacts, CI.

## Basic usage

### Command namespaces

FastSkill uses explicit namespaces. Root-level package and operational verbs, the plural
`repos` namespace, and implicit `fastskill <skill-id>` reading are not supported.

| Area | Commands |
|---|---|
| Skills and projects | `skill add/remove/update/list/read/search`, `bundle build/add/list/update/remove/override`, `project init/install` |
| Sources and distribution | `repo add/list/info/update/remove/test/refresh/skills/show/versions`, `marketplace create` |
| Quality | `analysis matrix/cluster/duplicates`, `eval validate/run/judge/report/score/scorecard`, `optimization run/resume/status/inspect/export` |
| Operations | `index rebuild`, `cache info/clean`, `server serve`, `mcp serve/install/list`, `cli doctor/completion/spec` |

### Adding skills

```bash
# From git repository
fastskill skill add https://github.com/org/skill.git

# From a git repository subdirectory (GitHub tree URL: tree/<branch>/<path/to/skill>)
fastskill skill add "https://github.com/org/repo/tree/main/path/to/skill"

# From a local folder
fastskill skill add ./local-skill

# Editable mode (symlink a local folder for development)
fastskill skill add ./local-skill -e

# Every skill under a local folder (recursive)
fastskill skill add ./skills -r

# From a configured repository. Omitted version and @latest select the newest stable release.
fastskill skill add scope/pptx --repository official
fastskill skill add scope/pptx@latest --repository official
fastskill skill add scope/pptx@1.0.0 --repository official

# From git with branch/tag
fastskill skill add https://github.com/org/skill.git --branch main
fastskill skill add https://github.com/org/skill.git --tag v1.0.0

# Add to a group
fastskill skill add https://github.com/org/skill.git --group dev

# Preview without changing state, or use only local/cached inputs
fastskill skill add scope/pptx --repository official --dry-run --json
fastskill skill add ./local-skill --offline
```

Use `ID@VERSION` for exact pins; `ID`, `ID@latest`, and wildcard references select the newest
stable compatible release. Prereleases are selected only by an explicit prerelease version or
constraint. A repository name is required when a bare ID could otherwise be ambiguous, and the
selected repository is retained in the Manifest and Lock provenance.

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

Install. Ordinary install resolves the Manifest while retaining compatible locked selections;
strict install restores only verified facts already covered by the Lock:

```bash
fastskill project install                 # resolve desired state, retaining compatible locked pins
fastskill project install --lock          # restore exact verified Lock facts; fail on incomplete coverage
fastskill project install --only prod     # only the prod group
fastskill project install --without dev   # everything except the dev group
fastskill project install --offline       # prohibit network access; use verified local/cached inputs
fastskill project install --dry-run --json
```

Roots without an explicit group belong to the implicit `default` group. Unknown group names are
errors. The same `--only` and `--without` selection rules apply with and without `--lock`.

### Building and managing team bundles

A bundle is a versioned ZIP containing selected skills, their dependency closure, resources, and
content digests. Declare every member in both `[bundle.members]` and `[dependencies]`:

```toml
schema_version = "1"

[bundle]
format = "fastskill-bundle-v1"
id = "platform-team"
version = "1.0.0"

[bundle.members.code-review]
overridable = false

[dependencies]
code-review = "2.1.0"
```

Build, install, inspect, update, and remove the bundle:

```bash
fastskill bundle build --output dist
fastskill bundle add dist/platform-team-1.0.0.zip
fastskill bundle list
fastskill bundle update platform-team --from ./platform-team-1.1.0.zip
fastskill bundle remove platform-team --force
```

Bundle build validates installed member versions against their dependency declarations.
`fastskill project install --lock` restores the exact bundle release recorded in `skills.lock`.
Do not remove a bundle member with `fastskill skill remove <skill-id>`; remove its owning bundle.
Use `skill add` for individual skills and `bundle add` for bundle artifacts; each rejects the
other artifact kind before changing project state. Bundle lifecycle commands require a project
and reject `--global`.
For an allowed customization, set `overridable = true` and run:

```bash
fastskill bundle override code-review --from ./my-code-review
fastskill bundle override code-review --reset
```

`--reset` validates the complete ownership plan, restores the packaged member, and removes the
personal override declaration. Use `--dry-run --json` to inspect override and reset plans.

### Listing, reading, and removing skills

```bash
fastskill skill list                    # list installed skills with reconciliation status
fastskill skill list --json             # machine-readable
fastskill skill list --check            # return nonzero when selected managed state needs repair
fastskill skill list --check --only prod
fastskill skill read my-skill-id        # print the skill's SKILL.md
fastskill skill read my-skill-id --meta # metadata only
fastskill skill read my-skill-id --tree # dependency tree
fastskill skill remove my-skill-id      # uninstall unless an installed bundle owns it
```

### Updating skills

```bash
fastskill skill update                                  # update all skills from recorded intent
fastskill skill update my-skill-id                      # update one skill
fastskill skill update my-skill-id --strategy patch     # latest | patch | minor | major
fastskill skill update my-skill-id --to-version 1.4.0 --repository official
fastskill skill update --check --json                   # resolve and report without writing
fastskill skill update --dry-run                        # validated preview
fastskill skill update --offline                        # prohibit network access
```

`--to-version` requires one repository-backed skill and an exact semantic version. `--repository`
also requires one repository-backed skill. `--source` is a deprecated alias of `--repository`.
Exact Manifest pins do not widen; ranged selections stay within their recorded constraint unless
an explicit version change is requested.

### Semantic search

```bash
fastskill index rebuild                 # build/refresh the local vector index
fastskill index rebuild --force         # force a full re-index

fastskill skill search "powerpoint presentation"        # remote catalogs (default)
fastskill skill search "data processing" --local        # installed skills
fastskill skill search "charts" --local --limit 5 --json
fastskill skill search "deploy service" --local --paths --json --content preview
fastskill skill read deployment-skill                    # retrieve the full selected skill
```

Search needs an embedding provider (`[tool.fastskill.embedding]` + `OPENAI_API_KEY`) for semantic ranking; without it, local search falls back to keyword matching. Skill add/update/remove and project install rebuild the index when `auto_reindex = true` (skipped silently if no embedding provider is configured); use `--no-reindex` to opt out.

For agent workflows, prefer `--local --paths --json --content preview` to discover candidate skill
files, then `fastskill skill read <id>` for the selected skill. Use `--content full` only when the caller
needs all matching documents in one response.

## Repository management

FastSkill manages skill sources through the `repo` command group. Repositories are stored in `[[tool.fastskill.repositories]]` in `skill-project.toml`.

```bash
# Add repositories (type: git-marketplace | http-registry | zip-url | local)
fastskill repo add team-skills --repo-type git-marketplace https://github.com/org/team-skills.git
fastskill repo add prod-registry --repo-type http-registry https://api.fastskill.io/index
fastskill repo add official --repo-type zip-url https://example.com/skills/
fastskill repo add local-dev --repo-type local ./local-skills

# Inspect and maintain
fastskill repo list                          # list configured repositories
fastskill repo info team-skills              # repository details
fastskill repo test team-skills              # connectivity check
fastskill repo update team-skills --branch main --priority 1
fastskill repo refresh                       # refresh cached catalog metadata
fastskill repo remove team-skills

# Browse catalogs
fastskill repo skills --repository prod-registry [--scope engineering] [--all-versions]
fastskill repo show engineering/data-analyzer --repository prod-registry
fastskill repo versions engineering/data-analyzer --repository prod-registry
```

Search across configured registries with `fastskill skill search "<query>" --repository <name>`.

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

`analysis` uses the semantic index to find overlap across skills (requires an embedding provider and an index — run `index rebuild` first).

```bash
fastskill analysis matrix --threshold 0.8        # pairwise similarity
fastskill analysis cluster -k 8 --min-size 2     # semantic clusters
fastskill analysis duplicates --threshold 0.92 --severity high   # near-duplicates
```

## Optimizing skills

`optimization` runs an automated text-gradient loop that improves a skill document against eval cases: propose a patch → run the target agent → grade → accept if the score improves → repeat, writing the best version to disk.

```bash
fastskill optimization run --config optimize.toml --out-dir ./optimize-runs
fastskill optimization status ./optimize-runs/<run> [--watch]
fastskill optimization resume ./optimize-runs/<run>
fastskill optimization inspect ./optimize-runs/<run> --step 3 --show all
fastskill optimization export ./optimize-runs/<run> --out ./best_skill.md
```

Scoring passes (rollouts, gate, baseline, final) are **isolated by default**: each case scores in a scratch workspace containing only the candidate skill. Set `isolate = false` in the config or pass `optimization run --no-isolation` to score against the machine's ambient environment instead; the decision is persisted into the run's provenance config so `resume` replays it. Baselines recorded before isolation existed will shift on the first isolated run.

## Serving skills (HTTP API and MCP)

Start a local server exposing an HTTP API and web UI:

```bash
fastskill server serve                                 # read-only by default
fastskill server serve --host 0.0.0.0 --port 8080
fastskill server serve --enable-write                  # enable state-changing endpoints
```

The server is **read-only by default** (ADR-0003): read endpoints (list/get skills, project, search, resolve, status, registry browse, dashboard) are always available; every write endpoint (install/update/remove/reindex/manifest edits) returns **HTTP 403** unless you start `server serve` with `--enable-write`. The server enforces **no authentication of its own** — run it local-first, or place an authenticating reverse proxy in front if you expose it.

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
# Read tools are exposed by default; mutating tools require --enable-write
fastskill mcp serve --transport stdio
fastskill mcp serve --transport stdio --enable-write
fastskill mcp serve --transport http --port 8080 --path /mcp

# Write MCP server config into an agent's config
fastskill mcp install --agent claude --scope project --stdio
fastskill mcp list
```

`mcp install` supports agents `claude`, `cursor`, `gemini`, `copilot`, `opencode`, and `codex`, at `--scope project` or `global`.

Without `--enable-write`, mutating tools are hidden from `tools/list` and rejected if called.
Generated tool names mirror the canonical path with underscores, including
`fastskill_skill_add`, `fastskill_bundle_remove`, and `fastskill_project_install`.

## Cache and automation utilities

```bash
fastskill cache info                  # cache path, entries, and disk usage
fastskill cache info --json
fastskill cache clean                 # clear every cached source
fastskill cache clean --source git    # git | registry | local | zip
fastskill cache clean --json

fastskill cli completion bash             # bash | zsh | fish | powershell | pwsh
fastskill cli spec --format json          # authoritative machine-readable CLI surface
fastskill cli spec --format markdown --output fastskill-cli.md
```

Use `fastskill cli spec` when an integration needs current command paths, arguments, defaults, or
examples. Do not maintain a hand-written command schema in an agent integration.

## Diagnostics

```bash
fastskill cli doctor          # check skills dir, skill-project.toml, embedding config, OPENAI_API_KEY, auth token
fastskill cli doctor --json
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
        run: fastskill project install --lock

      - name: Validate evals
        run: fastskill eval validate
```

Set `OPENAI_API_KEY` and any repository PAT env vars as CI secrets when your workflow uses search or private repositories.

## Troubleshooting

### "Embedding configuration required but not found"

1. Run `fastskill project init` (or add `[tool.fastskill.embedding]` to `skill-project.toml`).
2. Set `OPENAI_API_KEY`.
3. Re-run `fastskill index rebuild`.

### Repository source not appearing

- Verify `marketplace.json` exists at the expected location for `git-marketplace`.
- Confirm the repo `type` and URL are correct; run `fastskill repo test <name>`.

### Search returns nothing

- Run `fastskill index rebuild` to (re)build the index.
- Confirm `OPENAI_API_KEY` and `[tool.fastskill.embedding]` are set (`fastskill cli doctor`).

## Version management

FastSkill uses semantic versioning. A skill's version is read from the `[metadata]` section of its `skill-project.toml`.

## Additional resources

- **[Skill evals (`fastskill eval`)](references/eval.md)** — eval config, prompts CSV, checks TOML, running/scoring, artifacts.
- Full documentation: <https://docs.gofastskill.com/>
