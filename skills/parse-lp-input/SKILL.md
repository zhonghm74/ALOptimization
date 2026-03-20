---
name: parse-lp-input
description: Parse business documents into LP artifacts by dynamically creating a Python extractor script at runtime.
license: MIT
---

# parse-lp-input

## Purpose
read business documents and produce a complete, self-consistent LP problem definition.

## Triggers
- `parse lp input from markdown`
- `extract variables constraints objective by dynamic script`
- `generate parser outputs for solver pipeline`
- `extract report requirements and template`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| Input.document | file | Source business document (Markdown/TXT/CSV/Excel converted/normalized to text) |
| Input.command | shell | First create a temporary python parser under `scripts/`, then run it with `python3 <tmp_script>.py --input <doc> --output-dir <dir>` |
| Output.model_json | json | Structured LP definition with `variables`, `constraints`, `objective`, `metadata` |
| Output.problem_description_md | markdown | Business-level problem description extracted from source |
| Output.variable_name_map_cn | json | `{variable_name: chinese_name}` for all variables in `model_json.variables` |
| Output.report_requirements_md | markdown | Extracted report chapter requirements/checklist |
| Output.report_template_md | markdown | Extracted report writing template (for final report generation) |
| Output.parse_output_json | json | Output index file containing all generated artifact paths |

## Indexing and Expansion Policy
- Preserve indexed forms by default (`x[t,Ai]`, `y[t,Lj]`, `r[t,Ai]`, `c[t,Lj]`).
- Do not perform unnecessary Cartesian expansion for static parameters/constraints.
- Keep daily/cross-day constraints in quantified indexed form unless source explicitly requires expansion.
- Record assumptions in `metadata.assumptions`.

## Scripts
- No fixed parser script is checked in as the default implementation.
- The execution method is to dynamically create a Python script in `scripts/` for the current input/task, run it, and iterate until outputs are correct.
- Recommended temporary script naming:
  - `scripts/generated_parse_lp_input_<timestamp>.py`
  - `scripts/tmp_parse_lp_input.py`

## Script Lifecycle Policy
- Keep generated parser script after execution (do not delete by default).
- Preferred reusable path: `scripts/parse_lp_input.py` (or a stable configured path).
- Reuse-first decision:
  1. If script exists, run health checks first.
  2. Reuse only when all health checks pass.
  3. If script missing or health checks fail, regenerate/repair script, then rerun checks.
- Health checks must include all three categories:
  - **Requirement-fit check**: script logic matches current problem requirements (input type, expected outputs, indexing/expansion policy, report extraction scope).
  - **Output validation**: generated artifacts satisfy schema and completeness checks.
  - **Skill verification**: this skill's Verification checklist items are satisfied.

## Process

### Phase 1 - Reuse or (Re)Create Parser Script
- If a reusable parser script already exists in `scripts/`, run health checks first.
- If health checks pass, reuse existing script directly.
- If health checks fail or script is missing, create/repair parser script in `scripts/`.
- The generated script should implement extraction for:
  - LP model (`variables`, `constraints`, `objective`, `metadata`)
  - `problem_description_md`
  - `variable_name_map_cn`
  - `report_requirements_md` (from report chapter)
  - `report_template_md` (from report template section/code block)

### Phase 2 - Run Script to Extract Artifacts
- Run:
  - `python3 scripts/<generated_script>.py --input examples/alm_lp_full_test_input.md --output-dir examples`
- Expect these files:
  - `<stem>_parsed.json`
  - `<stem>_problem_description.md`
  - `<stem>_variable_name_map_cn.json`
  - `<stem>_report_requirements.md`
  - `<stem>_report_template.md`
  - `<stem>_parse_output.json`

### Phase 3 - Validate and Iterate Until Correct
- Validate schema and references (output validation):
  - all objective/constraint variables must exist in `variables`
  - all parameter variables must be explicitly listed in `variables`
- Validate report extraction:
  - requirements file includes mandatory chart/report requirements
  - template file contains reusable conclusion/report template
- Validate requirement-fit:
  - current script behavior matches current problem requirements
  - no stale assumptions from previous tasks
- Validate skill verification:
  - all checklist items in `Verification` pass
- If output is wrong/incomplete:
  - modify/re-generate the temporary parser script
  - rerun command
  - repeat until outputs are correct

## Verification
- [ ] Parser is dynamically created under `scripts/` and executed successfully.
- [ ] Running generated script produces all 6 output files.
- [ ] All objective variables appear in `variables`.
- [ ] All constraint term variables appear in `variables`.
- [ ] All parameter variables are explicitly listed in `variables`.
- [ ] Variable extraction follows source granularity (no unnecessary expansion).
- [ ] `variable_name_map_cn` covers every variable in `model_json.variables`.
- [ ] `problem_description_md` is consistent with `model_json`.
- [ ] `report_requirements_md` includes extracted report requirements.
- [ ] `report_template_md` includes an executable writing template.

## Anti-Patterns
- Do not rely on a stale fixed parser implementation when the task requires dynamic extraction.
- Do not reuse an existing script without checking requirement-fit for the current task.
- Do not manually hand-edit generated output as the primary workflow; fix generated script and rerun.
- Do not invent unsupported constraints/objectives.
- Do not skip parser rerun after script modifications.
- Do not output variables without Chinese mapping.

## Extension Points
- Add parsers for additional source formats (native CSV/Excel readers).
- Add confidence scores and extraction diagnostics.
- Add strict JSON schema validation for downstream solver/report skills.
