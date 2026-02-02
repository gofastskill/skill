# FastSkill Skill Repository

This repository contains FastSkill skill for Claude Code.

## Repository Structure

```
.
├── SKILL.md                     # Skill documentation
├── skill-project.toml             # Skill configuration and metadata
└── .github/
    └── workflows/
        └── publish-skill.yml  # CI/CD workflow for packaging and publishing
```

## Installation

Install this skill using FastSkill CLI:

```bash
fastskill add https://github.com/gofastskill/skill.git
```

## Development

To make changes to the skill:

1. Edit files in repository root (SKILL.md, skill-project.toml)
2. Commit and push to `main` branch
3. The CI/CD workflow will automatically package and publish a new release

## CI/CD

The GitHub Actions workflow in `.github/workflows/publish-skill.yml`:

- Detects changes to `SKILL.md` or `skill-project.toml`
- Packages skill using FastSkill CLI
- Creates a GitHub release with the packaged skill artifact
- Uses GitHub App token for release operations

## Required Secrets

The workflow requires the following repository secrets:

- `GH_APP_ID`: GitHub App ID for token generation
- `GH_APP_PRIVATE_KEY`: GitHub App private key for authentication
- `GITHUB_TOKEN`: Repository access token (automatically provided by GitHub Actions)

## License

Apache-2.0
