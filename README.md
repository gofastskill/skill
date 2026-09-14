# FastSkill Skill Repository

This repository contains the FastSkill skill for AI Agent Skills. Install it with the
FastSkill CLI to give agents current guidance for skill projects, packages, bundles,
repositories, evaluations, and operations.

## Installation

From your project root:

```bash
fastskill project init
fastskill skill add https://github.com/gofastskill/skill.git
```

Read the installed skill with `fastskill skill read fastskill`. The skill documents the
canonical command namespaces introduced by the breaking CLI migration; use a matching
FastSkill release.

The installed skill includes [guided eval authoring](fastskill/references/eval-authoring.md)
and a [copyable invoice example](fastskill/examples/invoice-extraction/).
Repository-only [evals](evals/README.md) measure the FastSkill skill itself; they are not
included in the released skill ZIP. See the [assessment and ownership record](specs/002-eval-authoring-consolidation.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and release details.

## License

Apache-2.0
