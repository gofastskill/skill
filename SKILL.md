---
name: fastskill
version: 1.0.0
description: Package manager and operational toolkit for Claude Code-compatible skills. Use this skill when installing, managing, packaging, publishing, or discovering skills; setting up skill registries; configuring repositories; implementing CI/CD workflows for skills; or performing semantic search across skill collections.
license: Apache-2.0
---

# FastSkill

FastSkill is a package manager and operational toolkit for Claude Code-compatible skills. It provides discovery, installation, versioning, deployment, and semantic search capabilities for skills at scale.

## Overview

FastSkill extends Anthropic's standardized Skills format with registry services, semantic search, version management, and deployment tooling. Use FastSkill to manage skill lifecycles from development to production distribution.

## Installation

Install FastSkill CLI:

```bash
# Quick install (recommended)
curl -fsSL https://raw.githubusercontent.com/gofastskill/fastskill/main/scripts/install.sh | bash

# Or via Homebrew (Linux)
brew install gofastskill/cli/fastskill

# Or via Scoop (Windows)
scoop bucket add gofastskill/scoop-bucket
scoop install fastskill

# Or via Cargo
cargo install fastskill
```

Verify installation:

```bash
fastskill --version
```

## Configuration

FastSkill uses `skill-project.toml` as a single configuration file for both project-level and skill-level contexts.

### Quick Setup

Initialize a new project with:

```bash
fastskill init
```

This creates a `skill-project.toml` with all sections properly configured.

### Configuration File Structure

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

### Environment Variables

```bash
export OPENAI_API_KEY="your-key-here"
export FASTSKILL_API_URL="https://registry.example.com"
```

## Basic Usage

### Skill Management

#### Adding Skills

Install skills from various sources:

```bash
# From git repository
fastskill add https://github.com/org/skill.git

# From local folder
fastskill add ./local-skill

# Editable mode (for development)
fastskill add ./local-skill -e

# From registry with version
fastskill add pptx@1.0.0

# From git with branch/tag
fastskill add https://github.com/org/skill.git --branch main
fastskill add https://github.com/org/skill.git --tag v1.0.0

# Add to group
fastskill add https://github.com/org/skill.git --group dev
```

#### Installing from Manifest

Create `skill-project.toml` with dependencies:

```toml
[dependencies]
web-scraper = { source = "git", url = "https://github.com/org/web-scraper.git" }
data-processor = { source = "git", url = "https://github.com/org/data-processor.git", group = "prod" }
```

Install all skills:

```bash
fastskill install

# Install with lock file (reproducible)
fastskill install --lock

# Install specific groups
fastskill install --only prod
fastskill install --without dev
```

#### Listing Skills

```bash
# List installed skills
fastskill show

# Remove skill
fastskill remove my-skill-id
```

#### Updating Skills

```bash
# Update all skills
fastskill update

# Update specific skill
fastskill update my-skill-id

# Check for updates without installing
fastskill update --check

# Dry run preview
fastskill update --dry-run
```

### Semantic Search

Index skills for semantic search:

```bash
# Index all skills
fastskill reindex

# Force re-index
fastskill reindex --force

# Control API concurrency
fastskill reindex --max-concurrent 3
```

Search indexed skills:

```bash
fastskill search "powerpoint presentation"
fastskill search "data processing" --limit 5
fastskill search "charts" --format json
```

## Repository Management

FastSkill provides a unified repository system for managing all skill storage locations.

### Git Marketplace Sources

Git marketplace sources reference Git repositories containing skills with marketplace.json.

**Configuration**:

```toml
[[tool.fastskill.repositories]]
name = "team-skills"
type = "git-marketplace"
url = "https://github.com/org/team-skills.git"
branch = "main"
priority = 0
```

**Commands**:

```bash
# Add repository
fastskill registry add team-skills --repo-type git-marketplace --url https://github.com/org/team-skills.git

# List repositories
fastskill registry list

# Show repository details
fastskill registry show team-skills

# Search across repositories
fastskill registry search "web scraping"

# Refresh cached sources
fastskill registry refresh

# Remove repository
fastskill registry remove team-skills
```

**Requirements**:
- Repository must contain `marketplace.json` in one of these locations:
  - `.claude-plugin/marketplace.json` (Claude Code standard)
  - `marketplace.json` (root, legacy support)

### HTTP Registry Sources

HTTP-based registries provide skills through REST APIs.

**Configuration**:

```toml
[[tool.fastskill.repositories]]
name = "production-registry"
type = "http-registry"
index_url = "https://api.fastskill.io/index"
priority = 0
auth = { type = "pat", env_var = "FASTSKILL_TOKEN" }
```

**Commands**:

```bash
# Add HTTP registry
fastskill registry add prod-registry --repo-type http-registry --url https://api.fastskill.io/index

# List skills from registry
fastskill registry list-skills --repository prod-registry

# List skills by scope
fastskill registry list-skills --repository prod-registry --scope engineering

# List skills with all versions
fastskill registry list-skills --repository prod-registry --scope engineering --all-versions

# Get skill details
fastskill registry show-skill engineering/data-analyzer --repository prod-registry

# List skill versions
fastskill registry versions engineering/data-analyzer --repository prod-registry

# Search skills in registry
fastskill registry search "data analysis" --repository prod-registry
```

### ZIP URL Sources

Static hosting with pre-packaged ZIP archives.

**Configuration**:

```toml
[[tool.fastskill.repositories]]
name = "official-skills"
type = "zip-url"
base_url = "https://example.com/skills/"
priority = 0
```

**Commands**:

```bash
# Add ZIP URL repository
fastskill registry add official-skills --repo-type zip-url --url https://example.com/skills/
```

### Local Sources

Local filesystem paths for development.

**Configuration**:

```toml
[[tool.fastskill.repositories]]
name = "local-dev"
type = "local"
path = "./local-skills"
priority = 0
```

**Commands**:

```bash
# Add local repository
fastskill registry add local-dev --repo-type local --url ./local-skills
```

## Packaging Skills

Package skills into ZIP artifacts for distribution.

### Package Command Options

| Option | Description | Default |
|---------|-------------|---------|
| `--detect-changes` | Auto-detect changed skills using file hash comparison | `false` |
| `--git-diff <BASE> <HEAD>` | Use git diff for change detection | None |
| `--skills <IDS...>` | Package specific skills by ID | None |
| `--bump <major\|minor\|patch>` | Bump version type | None |
| `--auto-bump` | Auto-detect bump type from changes | `false` |
| `--output <DIR>` | Output directory for artifacts | `./artifacts` |
| `--force` | Package all skills regardless of changes | `false` |
| `--dry-run` | Show what would be packaged without actually packaging | `false` |
| `--skills-dir <DIR>` | Skills directory to scan | `./skills` |
| `--recursive` | Recursively scan skills directory | `false` |

### Usage Examples

#### Auto-detect Changed Skills

```bash
fastskill package --detect-changes --output ./artifacts
```

#### Git-based Change Detection

```bash
fastskill package --git-diff HEAD~1 HEAD --output ./artifacts
```

#### Version Bumping

```bash
# Bump minor version
fastskill package --detect-changes --bump minor --output ./artifacts

# Bump patch version
fastskill package --detect-changes --bump patch --output ./artifacts
```

#### Package Specific Skills

```bash
fastskill package --skills web-scraper data-processor --output ./artifacts
```

#### Force Package All Skills

```bash
fastskill package --force --output ./artifacts
```

#### Package All Skills Recursively

```bash
fastskill package --recursive --force --output ./artifacts
```

### Artifact Structure

Each packaged skill creates a ZIP file:

```
skill-id-version.zip
├── SKILL.md
├── skill-project.toml
├── scripts/
├── references/
├── assets/
├── BUILD_INFO.json
└── CHECKSUM.sha256
```

### Build Cache

The command maintains a build cache at `.fastskill/build-cache.json` that tracks skill versions, file hashes, and artifact paths.

## Publishing Skills

Publish skill packages to registries.

### Authentication

```bash
# Login to registry
fastskill auth login

# Check identity
fastskill auth whoami

# Or use token directly
echo "your-jwt-token" | fastskill auth login --token-stdin
```

### Publish Command Options

| Option | Description | Default |
|---------|-------------|---------|
| `--artifacts <PATH>` | Package file or directory | `./artifacts` |
| `--target <TARGET>` | API URL or local folder path | `FASTSKILL_API_URL` |
| `--wait` | Wait for validation | `true` |
| `--no-wait` | Don't wait for validation | `false` |
| `--max-wait <SECONDS>` | Maximum wait time (seconds) | `300` |

### Usage Examples

```bash
# Publish to registry API
fastskill publish --artifacts ./artifacts --target https://registry.example.com

# Publish single package
fastskill publish --artifacts ./artifacts/my-skill-1.0.0.zip --target https://registry.example.com

# Publish to local folder
fastskill publish --artifacts ./artifacts --target ./local-registry

# Don't wait for validation
fastskill publish --artifacts ./artifacts --target https://registry.example.com --no-wait
```

### Scope Management

The server automatically extracts scope from your JWT token's user account:

- **Organization users**: `"org/user"` → scope `"org"`
- **Individual users**: `"user"` → scope `"user"`

Example skill IDs:

- `acme/web-scraper` (scope: acme)
- `personal/tool` (scope: personal)

## Server and HTTP API

Start FastSkill HTTP server:

```bash
# Start API server
fastskill serve

# Start with web UI
fastskill serve --enable-registry

# Custom host and port
fastskill serve --host 0.0.0.0 --port 8080 --enable-registry
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/registry/skills/search?query=<term>` | GET | Search skills by query |
| `/api/registry/index/skills` | GET | List all skills from registry index |
| `/api/registry/skills/:skill_id` | GET | Get skill metadata |
| `/api/registry/skills/:skill_id/versions` | GET | List versions for a skill |
| `/api/registry/skills/:skill_id/:version/download` | GET | Download skill package (302 redirect) |
| `DELETE /api/registry/skills/:skill_id/:version/yank` | DELETE | Yank a version |
| `PUT /api/registry/skills/:skill_id/:version/unyank` | PUT | Unyank a version |

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Publish Skills

on:
  push:
    branches: [main]
    paths:
      - 'skills/**'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install FastSkill
        run: |
          curl -fsSL https://raw.githubusercontent.com/gofastskill/fastskill/main/scripts/install.sh | bash
      
      - name: Package changed skills
        run: |
          fastskill package --git-diff HEAD~1 HEAD --auto-bump --output ./artifacts
      
      - name: Publish to registry
        env:
          FASTSKILL_API_URL: ${{ secrets.FASTSKILL_API_URL }}
          FASTSKILL_API_TOKEN: ${{ secrets.FASTSKILL_API_TOKEN }}
        run: |
          fastskill publish --artifacts ./artifacts
```

### GitLab CI Example

```yaml
stages:
  - package
  - publish

package:
  stage: package
  script:
    - fastskill package --git-diff $CI_COMMIT_BEFORE_SHA $CI_COMMIT_SHA --auto-bump --output ./artifacts
  artifacts:
    paths:
      - artifacts/

publish:
  stage: publish
  script:
    - echo "$FASTSKILL_API_TOKEN" | fastskill auth login --token-stdin
    - fastskill publish --artifacts ./artifacts
```

## Troubleshooting

### Configuration Not Found

If you see "Embedding configuration required but not found":

1. Run `fastskill init` to create `skill-project.toml`
2. Add `[tool.fastskill.embedding]` section with embedding configuration
3. Set `OPENAI_API_KEY` environment variable

### Source Not Appearing in Registry

- Verify `marketplace.json` exists at expected URL
- Check source type is `git-marketplace` or `zip-url`
- Ensure URL is accessible

### Publish Failures

- Verify authentication credentials
- Check registry API URL
- Ensure registry server is running

### Search Not Working

- Run `fastskill reindex` to rebuild index
- Verify OpenAI API key is set
- Check embedding configuration

## Version Management

FastSkill uses semantic versioning (semver):

- **Major**: Breaking changes (1.2.3 → 2.0.0)
- **Minor**: New features (1.2.3 → 1.3.0)
- **Patch**: Bug fixes (1.2.3 → 1.2.4)

Version is read from `skill-project.toml` [metadata] section.

## Additional Resources

See [Reference Guide](references/SKILL-REFERENCE.md) for:
- Complete command reference with all options
- Advanced usage patterns
- Repository management details
- Authentication and scope handling
- API server configuration
- CI/CD workflow templates
