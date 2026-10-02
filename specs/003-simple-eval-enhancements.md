# Lightweight eval enhancements and verification

Based on main `cff04156f449199a9fe43ad93e2d13bc9f8af1e2`, 2026-09-29.
Implementation is restricted to the skills repository; no CLI/engine feature was added.

## Decisions

- Offer six cases / one trial / no judge as the quick path; keep the benchmark opt-in.
- Name whole-trace substring matching honestly. It can match an incorrect command or
  tool result; it is not answer accuracy. Regression fixtures preserve these contrasts.
- Remove the incorrect no-publish literal prohibition. Correctness for that case is
  judge-only, and advisory until calibrated. A deterministic pass is not semantic approval.
- Provide labelled judge contrasts, without pretending a judge calibration was executed.
- Offer only the configured Claude gateway route in hosted CI. Local scripts still accept
  other supported/authenticated runtimes. Forward the target model explicitly.
- CI verifies the intended failure check, not merely nonzero process status.
- Preserve original metadata and per-trial paths in the consultation negative control.
- Provide create/repair/extend tasks for a chosen authoring agent, with deterministic
  outcome/preservation verification. Do not add another model orchestrator.

## Verification on server02

FastSkill 0.9.235; 29 Python tests passed. The six-case smoke validates without a judge;
instrumented Bash tests also pass. Namespace validation and the payload guard pass.
Generated suite files are tested byte-identical after regeneration. Real offline scoring
checks both original fixtures and synthetic counterexamples. The negative control was
tested through the scorer with distinct paths on two trials and unchanged source bytes.

coverage.py branch instrumentation for changed Python source:

| File | Statements | Branches |
| --- | --- | --- |
| `evals/authoring/workflow.py` | 81/84 (96.43%) | 31/34 (91.18%) |
| `evals/v2/build.py` | 69/71 (97.18%) | 16/18 (88.89%) |
| `evals/v2/negctl.py` | 75/78 (96.15%) | 28/32 (87.50%) |

kcov Bash line coverage: `run.sh` 56/61 (91.80%), `stage.sh` 19/19 (100%),
`smoke.sh` 15/15 (100%). The runner's five continued argument lines are not attributed.
Bash branch instrumentation is unavailable. Staging's unchanged embedded Python is
excluded from the Bash count; its earlier independent coverage is in spec 002.

Raw evidence is outside the checkout in the sibling
`fastskill-eval-suite-enhancements-evidence/` directory.

## Changed-file coverage inventory

| File(s) | Evidence |
| --- | --- |
| `.github/workflows/skill-evals.yml` | Same unittest commands executed; negative fixture requires expected check; hosted execution pending |
| `README.md`, `CONTRIBUTING.md`, `evals/README.md`, `evals/v2/README.md` | Commands matched to executed smoke staging/validation and helper tests; limitations explicit |
| `evals/checks.toml` | Real positive/negative fixture rescoring; comment-only change |
| `evals/v2/patterns.json`, `evals/v2/correctness/checks.toml` | Regeneration equality; real scorer accepts correct refusal; suite validation |
| `evals/v2/metrics.toml` | Parsed metric selects fragment cases, excludes judge-only refusal; semantic label regression assertion |
| `evals/v2/calibration.json` | Known case IDs, labelled positive/negative pairs checked; no judge performance claim |
| `evals/v2/build.py` | In-process regeneration, TOML escaping, missing-prompt failure; coverage above |
| `evals/v2/smoke/prompts.csv`, `evals/v2/smoke/checks.toml` | Real validation: six cases, two negatives, no judge; regeneration equality |
| `evals/smoke.sh` | Recording runtime stub checks model/trials/error propagation and output preservation; line coverage above |
| `evals/v2/run.sh`, `evals/v2/stage.sh` | Seven shell/smoke tests including failures and preservation; line coverage above |
| `evals/v2/negctl.sh`, `evals/v2/negctl.py` | Actual scorer contrast, two per-trial paths, source-byte preservation, specific verdict checks |
| `evals/authoring/workflow.py` | Create, repair, extend; real validator; deliberately broken files/rows/notes rejected; coverage above |
| `scripts/test_authoring_workflows.py`, `scripts/test_eval_generation.py`, `scripts/test_eval_negctl.py`, `scripts/test_eval_scoring.py`, `scripts/test_eval_smoke.py`, `scripts/test_eval_scripts.py` | All discovered and executed; deliberate invalid/error inputs detected |
| `specs/003-simple-eval-enhancements.md` | Reconciled with current recorded results |

## Not established by these checks

No paid target sweep, new live authoring run, or native-judge calibration was performed.
The workflow helpers' deterministic test edits are not live model evidence. Human review
is still needed for semantic quality, expectation independence and answer leakage.
Hosted CI uses moving tool releases and logs versions; fully pinned reproducibility is
not claimed. The judge remains advisory and reference-based, not proof a command executes.
Changes to metric membership mean the revised fragment rate is not comparable to the
historical 12-case accuracy-labelled baseline. No deployment or merge is part of this change.
