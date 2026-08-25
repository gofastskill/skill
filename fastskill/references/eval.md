# Skill evaluations (`fastskill eval`)

This guide matches the FastSkill CLI implementation: configuration is read from `skill-project.toml`, cases from a prompts CSV, optional scoring rules from a checks TOML, and execution uses **aikit-sdk** (`run_agent_events`) with a supported agent CLI.

## What evals are for

Evals run repeatable prompts against a real agent in a working directory derived from your skill project root. You can record stdout, stderr, a JSONL trace, and per-case results under a timestamped run directory. Optional **checks** assert properties of that output (substring expectations, file presence, tool-call count).

## Prerequisites

1. **FastSkill CLI** installed (`fastskill --version`).
2. A **`skill-project.toml`** reachable from the current directory (FastSkill walks up the tree to find it).
3. **`[tool.fastskill.eval]`** present with a valid `prompts` path (see below).
4. For **`fastskill eval run`**: a **runnable agent** installed and on `PATH`. Agent keys are a closed set defined by aikit-sdk: `claude`, `codex`, `cursor`, `gemini`, `opencode`, `pi`, `aikit` — the last runs in-process and needs no CLI. If `fail_on_missing_agent = true` (default), the CLI refuses to run when the chosen agent is missing.

   `--agent` is validated against the agents **detected on the current machine**, not against the full key list. An agent is "detected" when its CLI is on `PATH` and answers `--version`. So a supported-but-not-installed key fails exactly like a typo:

   ```
   RUNTIME_UNKNOWN_ID: Unknown runtime ID(s): opencode. Available: aikit, claude, codex, cursor, gemini, pi
   ```

   If you get this for a key spelled correctly, install that agent's CLI — the `Available:` list reports what was found locally, so it differs from machine to machine and from the list above.

Evals do **not** require embedding or `OPENAI_API_KEY` unless your workflow also uses `reindex` / `search`.

## 1. Configure `skill-project.toml`

Add a `[tool.fastskill.eval]` table. Paths are resolved relative to the **skill project root** (directory containing `skill-project.toml`) unless absolute.

| Field | Required | Default | Meaning |
|--------|----------|---------|---------|
| `prompts` | yes | — | Path to the prompts CSV file. |
| `checks` | no | none | Path to checks TOML. If omitted, checks are not loaded. |
| `timeout_seconds` | no | `900` | Per-case timeout passed to the agent run. |
| `fail_on_missing_agent` | no | `true` | If true, `eval run` and `eval validate --agent <key>` error when the agent is not available. |

Example:

```toml
[tool.fastskill.eval]
prompts = "evals/prompts.csv"
checks = "evals/checks.toml"
timeout_seconds = 600
fail_on_missing_agent = true
```

### Validate configuration

From the skill project (or any subdirectory under it):

```bash
fastskill eval validate
fastskill eval validate --agent codex
fastskill eval validate --json
```

Errors use stable prefixes: `EVAL_CONFIG_MISSING`, `EVAL_PROMPTS_NOT_FOUND`, `EVAL_AGENT_UNAVAILABLE`.

## 2. Define cases: prompts CSV

The suite loader expects a header row and **required** columns: `id`, `prompt`, `should_trigger`.

Optional columns: `tags`, `workspace_subdir`.

- **`id`**: non-empty identifier per row (used for `--case`, artifact folder names, and reports).
- **`prompt`**: text sent to the agent; use CSV quoting for commas or newlines (`"..."`, escaped `""` inside quotes).
- **`should_trigger`**: `true` / `false` / `1` / other (treated false). Documented intent only; **pass/fail is not driven by this column**. When no checks file is configured, a case **passes** if the agent exits with code `0`, **fails** otherwise. When checks are loaded, a case **passes** only if **every** check passes (see below).
- **`tags`**: comma-separated tags inside the cell (e.g. `smoke,basic`). Used with `eval run --tag <name>`.
- **`workspace_subdir`**: path relative to skill project root; if set, that directory is the agent’s current working directory for the case. If empty or column omitted, cwd is the project root.

Example:

```csv
id,prompt,should_trigger,tags,workspace_subdir
smoke-1,"List fastskill subcommands briefly",true,smoke,
deep-1,"Explain eval validate flags",true,docs,
```

Empty lines are skipped.

## 3. Define checks: `checks.toml` (optional)

Point `checks` in TOML at a file containing one or more `[[check]]` tables. Each check must include **`name`**, selecting the check type. Optional **`required`** (boolean, default `true`) is accepted on all types for schema compatibility; the runner currently treats a case as failed if **any** check fails.

### `trigger_expectation`

Substring search in **combined** stdout and trace JSONL. `expected = true` means the pattern must appear; `expected = false` means it must not.

```toml
[[check]]
name = "trigger_expectation"
pattern = "fastskill eval"
expected = true
required = true
```

### `command_contains`

True if the pattern appears anywhere in the same combined stdout + trace string (literal substring).

```toml
[[check]]
name = "command_contains"
pattern = "validate"
required = true
```

### `file_exists`

True if `path` exists under the case **working directory** (project root or `project_root / workspace_subdir` for that case).

```toml
[[check]]
name = "file_exists"
path = "report.txt"
required = true
```

### `max_tool_calls`

Counts **tool calls** in `trace.jsonl` — trace events whose payload is typed `tool_use` (a structured tool invocation the agent made) or `raw_json` (a line the agent's backend emitted that FastSkill's aikit version does not yet model). Passes if count ≤ `limit`.

Agent prose is **not** a tool call: `message` and `reasoning` events are never counted.

```toml
[[check]]
name = "max_tool_calls"
limit = 20
required = true
```

> **Renamed.** This check was `max_command_count`. The old name still parses, so existing `checks.toml` files keep working, but results report the check as `max_tool_calls`. Use the new name in new files.
>
> **Re-baseline your limits if you set them before FastSkill 0.9.192.** Earlier versions counted only `raw_json`, which for some agents (notably `codex`) meant *every* trace line — including plain text — while structured tool calls counted as zero. The same agent behaviour can therefore produce a very different number now, usually a much smaller one. A limit tuned against the old count is not measuring what you think it is.

Parse/load errors: `EVAL_CHECKS_INVALID`.

### Scoring rules when checks are present

- Timeout: case status **`error`** (checks are not used to override that).
- If **`checks` is empty** (no file or file loads zero checks): pass iff exit code is `0`.
- If **any check** is loaded: case **`passed`** only if **every** check’s `passed` is true (see `run_checks` / `CaseResult` in the codebase).

## 4. Run evals

```bash
fastskill eval run --agent codex --output-dir ./eval-runs
fastskill eval run --agent claude --output-dir /tmp/evals --case smoke-1
fastskill eval run --agent codex --output-dir ./evals --tag smoke --model gpt-4o
fastskill eval run --agent codex --output-dir ./evals --json
```

- **`--output-dir`**: base directory; a subdirectory is created per run (`YYYY-MM-DDTHH-MM-SSZ`, with numeric suffix if needed).
- **`--no-fail`**: still prints failures but exits `0` (for CI that only collects artifacts).

Non-zero exit on suite failure unless `--no-fail`.

## 5. Artifacts

Under each run directory:

- **`summary.json`**: suite-level metadata (`suite_pass`, agent, model, paths, per-case summaries).
- **`<case-id>/stdout.txt`**, **`stderr.txt`**, **`trace.jsonl`**, **`result.json`** (`CaseResult`, including `check_results`).

`eval score` needs `summary.json` to include `checks_path` (written on `eval run` when checks were configured).

## 6. Report and re-score

```bash
fastskill eval report --run-dir ./eval-runs/2026-04-07T12-00-00Z
fastskill eval report --run-dir ./eval-runs/2026-04-07T12-00-00Z --json
```

Re-run deterministic checks on saved stdout/trace without invoking the agent:

```bash
fastskill eval score --run-dir ./eval-runs/2026-04-07T12-00-00Z
```

**Note:** `eval score` applies `file_exists` relative to **`skill_project_root`** from `summary.json`, not per-case `workspace_subdir`. If you rely on subdirectory-specific files, prefer re-running `eval run` or align check paths with that root.

## 7. Packaging and CI

- **`fastskill package`** excludes an `evals/` tree from published ZIPs (local eval suites are not shipped). Keep prompts/checks under `evals/` or paths you do not publish if you treat evals as repo-only.
- In CI, install the CLI and the agent you pass to `--agent`, add `[tool.fastskill.eval]`, then run `eval validate` and `eval run` with a writable `--output-dir`.

## Quick checklist

1. `[tool.fastskill.eval]` with existing `prompts` CSV path.
2. CSV header: `id`, `prompt`, `should_trigger` (+ optional `tags`, `workspace_subdir`).
3. Optional `checks` TOML with `[[check]]` and correct `name` / fields.
4. `fastskill eval validate` (and optionally `--agent <key>`).
5. `fastskill eval run --agent <key> --output-dir <dir>`.
6. Inspect `summary.json` and per-case `result.json` / `trace.jsonl`.
