# Eval authoring ownership and existing harness assessment

The installable FastSkill skill lives in `fastskill/`. Eval authoring is a workflow
of that skill: `fastskill/SKILL.md` routes to `references/eval-authoring.md`, the
supporting references, and a copyable `examples/invoice-extraction/` project.
There is no second top-level authoring skill or dependency on a CLI source checkout.

## Assessment of the existing evals directory

`evals/` is useful repository test infrastructure, not a competing authoring skill.
Keep it outside the released ZIP so its answers and regression fixtures are not
part of the payload being evaluated.

| Existing asset | Assessment and disposition |
| --- | --- |
| v1 prompts/checks and pass/fail fixtures | Keep: fast offline parser/scorer regression coverage. Fixture scoring is engine evidence, not a live quality baseline. |
| v2 patterns, generator, consultation/restraint/correctness suites | Keep: explicit case scope and separate metrics avoid conflating consultation with correct answers. Generation and namespace checks pass. |
| vacuity guard | Keep: scans the full packaged payload for answer-pattern leakage. Recheck after adding references/examples. It cannot prove semantic correctness or all forms of leakage. |
| correctness judge and reference answers | Keep: semantic review can catch invalid commands that substring checks accept. Its thresholds are advisory; parsing does not establish judge quality. |
| historical pi baseline | Keep as historical evidence only. It predates the current check/command changes and must not be presented as a current baseline. No full paid sweep was repeated for this relocation. |
| stage.sh | Repair: unconditional deletion of an arbitrary destination could destroy user files or a saved run's project. Refuse existing destinations; each sweep now allocates a fresh stage. |
| run.sh | Repair: subset runtime failures were logged but exited successfully. Propagate the error after retaining results/logs. |
| negctl.sh | Retain as a diagnostic with limitations: it assumes one common skill path across trials and rewrites a synthetic summary. Its output is a mutation control, not an original live run. It does not independently assert the tool-budget metric stayed unchanged. |
| CI and contributor guidance | Repair stale claims that v2 is never validated and Codex cannot supply consultation evidence. Preserve dispatch-only live runs. |
| packaged eval reference | Repair contradictory empty-check scoring and credential guidance. Keep it as the schema reference, linked from authoring. |

The old authoring assets in gofastskill/fastskill PR #333 move here. Their workflow
fixtures live in `evals/authoring/fixtures/`; executable asset tests live in
`scripts/test_eval_authoring.py`. CLI engine contract tests stay in the CLI repository.

## Verification boundaries

The earlier Claude/Codex authoring, continuation, defect/correction, and native-judge
contrasts remain evidence for the carried-over workflow. They do not prove the new
packaging/discovery path. That path must be checked by extracting the release ZIP,
following its local references, validating its example, and exercising installation.
The CLI report retains the original raw-evidence locations and historical results.

Run on Linux with the candidate FastSkill binary on PATH:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/check-command-namespaces.py
python3 evals/v2/build.py
git diff --exit-code -- evals/v2/consultation evals/v2/restraint evals/v2/correctness
python3 evals/v2/guard_vacuity.py
```

These checks make no model calls. Actual native judge calls require explicit endpoint,
model, and credential configuration; the shipped example retains placeholders.

## Observed relocation checks

On server02 with pinned FastSkill 0.9.230:

- All 12 Python tests passed (four authoring, five shell, three namespace tests).
  Namespace checks and regeneration parity passed; the vacuity guard scanned 15
  shipped payload files without finding any of its 12 answer patterns.
- The published ZIP layout installed successfully as FastSkill skill 2.1.0 in a temporary
  project. The installed entrypoint and authoring reference were present, and its copied
  invoice example validated (three cases, one check, one judge).
- All preserved v2 suites validated: consultation 22 cases, restraint eight cases, and
  correctness 12 cases with its judge. The v1 positive fixture passed and negative fixture
  failed for missing consultation. No new full live baseline is claimed.
- Six CLI engine contract tests and 13 CLI documentation/related tests passed after the move.
- kcov 38 measured `run.sh` at 54/58 executable Bash lines (93.1%) and `stage.sh` at 19/19
  Bash lines (100%). The four runner continuation lines are not attributed by the collector.
  The exact embedded Python body was extracted unchanged and measured separately with
  coverage.py: five statements covered, 100%, no branches. It is excluded from the Bash
  denominator. Bash branch coverage is unsupported by this collector, not claimed as passing.
- The five shell tests pass with instrumentation; the unconditional failing-child test runs
  directly because kcov 38 suppresses its output. The controllable full-run stub separately
  exercises the instrumented runtime-error path. Raw coverage is in the sibling CLI evidence
  directory under `shell-coverage-v2/` and `embedded-coverage-6f4x9rtk/`.

The original two-authoring-tool evidence remains in the CLI report. A scoped Claude
Sonnet 4.5 follow-up used the explicitly supplied installed entrypoint with file tools
only. It extended an existing suite with an unrelated negative-trigger case and wrote
`REVIEW.md` describing limitations. Independent caller validation passed for both cases;
the original positive row, checks, fixtures, user note, and installed skill were preserved.
This verifies installed-package routing and suite extension, not automatic discovery or
live target execution. Evidence: `relocation-authoring-result.json` and
`package-smoke-hHkVYA/` in the sibling CLI evidence directory.

## Changed-file coverage inventory

| File | Evidence |
| --- | --- |
| `.github/workflows/skill-evals.yml` | Same deterministic test command executed locally; PR CI result reported separately |
| `CONTRIBUTING.md` | Commands/links reviewed against actual workflow and validation output |
| `README.md` | Commands/links reviewed against actual workflow and validation output |
| `evals/authoring/fixtures/defective-total/SKILL.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/defective-total/ground-truth.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/environment-variants.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/existing-suite/SKILL.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/existing-suite/evals/checks.toml` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/existing-suite/evals/prompts.csv` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/existing-suite/evals/user-note.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/existing-suite/fixtures/release.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/existing-suite/skill-project.toml` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/invoice-no-evals/SKILL.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/invoice-no-evals/fixtures/ambiguous-date.txt` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/invoice-no-evals/fixtures/basic.txt` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/invoice-no-evals/fixtures/missing-number.txt` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/invoice-no-evals/fixtures/multiple-currencies.txt` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/scripted-workflow.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/unnecessary-step/SKILL.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/unnecessary-step/scripted-answers.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/authoring/fixtures/unsupported-order/SKILL.md` | Byte-identical relocation; original workflow/fixture evidence retained in CLI report |
| `evals/v2/README.md` | Commands/links reviewed against actual workflow and validation output |
| `evals/v2/run.sh` | Five shell scenarios; kcov 93.1% lines; runtime failures propagate |
| `evals/v2/stage.sh` | Existing directory/symlink preservation, fresh staging; Bash and embedded Python 100% lines |
| `fastskill/SKILL.md` | Packaged local-link checks; namespace validation; installed-package authoring smoke |
| `fastskill/examples/invoice-extraction/SKILL.md` | ZIP extraction and installation; copied example validation; independent invoice-fact checks |
| `fastskill/examples/invoice-extraction/evals/checks.toml` | ZIP extraction and installation; copied example validation; independent invoice-fact checks |
| `fastskill/examples/invoice-extraction/evals/judge-prompt.md` | ZIP extraction and installation; copied example validation; independent invoice-fact checks |
| `fastskill/examples/invoice-extraction/evals/prompts.csv` | ZIP extraction and installation; copied example validation; independent invoice-fact checks |
| `fastskill/examples/invoice-extraction/evals/review-notes.md` | ZIP extraction and installation; copied example validation; independent invoice-fact checks |
| `fastskill/examples/invoice-extraction/fixtures/basic.txt` | ZIP extraction and installation; copied example validation; independent invoice-fact checks |
| `fastskill/examples/invoice-extraction/fixtures/missing-number.txt` | ZIP extraction and installation; copied example validation; independent invoice-fact checks |
| `fastskill/examples/invoice-extraction/skill-project.toml` | ZIP extraction and installation; copied example validation; independent invoice-fact checks |
| `fastskill/references/eval-authoring.md` | Packaged local-link checks; namespace validation; installed-package authoring smoke |
| `fastskill/references/eval-authoring/examples.md` | Packaged local-link checks; namespace validation; installed-package authoring smoke |
| `fastskill/references/eval-authoring/handoff.md` | Packaged local-link checks; namespace validation; installed-package authoring smoke |
| `fastskill/references/eval-authoring/semantics.md` | Packaged local-link checks; namespace validation; installed-package authoring smoke |
| `fastskill/references/eval.md` | Packaged local-link checks; namespace validation; installed-package authoring smoke |
| `fastskill/skill-project.toml` | Version parity and real ZIP installation as 2.1.0 |
| `scripts/test_eval_authoring.py` | Unittest discovery and execution; deliberate contradiction/runtime failures detected |
| `scripts/test_eval_scripts.py` | Unittest discovery and execution; deliberate contradiction/runtime failures detected |
| `specs/002-eval-authoring-consolidation.md` | Commands/links reviewed against actual workflow and validation output |
