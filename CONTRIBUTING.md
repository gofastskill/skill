# Contributing to FastSkill Skill

## Repository Structure

```
gofastskill/skill/
├── skill-project.toml            # Repository configuration (project-level)
└── fastskill/                    # FastSkill skill subdirectory
    ├── SKILL.md                  # Skill documentation
    └── skill-project.toml        # Skill configuration and metadata
```

## Development

1. Edit files in `fastskill/` subdirectory
2. Commit and push to `main` branch
3. The CI/CD workflow will automatically package and publish a new release

## CI/CD

The GitHub Actions workflow in `.github/workflows/publish-skill.yml`:

- Detects changes to `fastskill/` directory
- Packages skill using FastSkill CLI
- Creates a GitHub release with the packaged skill artifact
- Uses GitHub App token for release operations

## Required Secrets

The workflow requires the following repository secrets:

- `GH_APP_ID`: GitHub App ID for token generation
- `GH_APP_PRIVATE_KEY`: GitHub App private key for authentication
- `GITHUB_TOKEN`: Repository access token (automatically provided by GitHub Actions)
