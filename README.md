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

## Quick self-test

From a clone, with FastSkill and an authenticated agent installed:

```bash
bash evals/smoke.sh claude ./smoke-results
```

Six cases, one trial each, no native judge. The output directory must be new. An optional
third argument selects the target model. This checks consultation, restraint and trace
fragments, **not semantic answer accuracy**, and costs agent tokens. See the
[eval guide](evals/README.md) for the optional benchmark and authoring workflow exercises.

## License

Apache-2.0
