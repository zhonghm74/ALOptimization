---
name: parse-lp-input
description: Parse business documents into LP artifacts with a runnable Python extractor.
license: MIT
---

# parse-lp-input

## Purpose
read business documents and produce a complete, self-consistent LP problem definition.

## Triggers
- `parse lp input from markdown`
- `extract variables constraints objective by script`
- `generate parser outputs for solver pipeline`
- `extract report requirements and template`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| Input.document | file | Source business document (Markdown/TXT/CSV/Excel converted/normalized to text) |
| Input.command | shell | `python3 skills/parse-lp-input/scripts/parse_lp_input.py --input <doc> --output-dir <dir>` |
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
- `scripts/parse_lp_input.py`
  - Parses LP model elements from source document.
  - Generates all output files listed in I/O Contract.
  - Performs consistency checks and exits non-zero on validation failure.

## Process

### Phase 1 - Create/Adjust Parser Script
- Ensure parser logic lives in `skills/parse-lp-input/scripts/parse_lp_input.py`.
- Implement extraction for:
  - LP model (`variables`, `constraints`, `objective`, `metadata`)
  - `problem_description_md`
  - `variable_name_map_cn`
  - `report_requirements_md` (from report chapter)
  - `report_template_md` (from report template section/code block)

### Phase 2 - Run Script to Extract Artifacts
- Run:
  - `python3 skills/parse-lp-input/scripts/parse_lp_input.py --input examples/alm_lp_full_test_input.md --output-dir examples`
- Expect these files:
  - `<stem>_parsed.json`
  - `<stem>_problem_description.md`
  - `<stem>_variable_name_map_cn.json`
  - `<stem>_report_requirements.md`
  - `<stem>_report_template.md`
  - `<stem>_parse_output.json`

### Phase 3 - Validate and Iterate Until Correct
- Validate schema and references:
  - all objective/constraint variables must exist in `variables`
  - all parameter variables must be explicitly listed in `variables`
- Validate report extraction:
  - requirements file includes mandatory chart/report requirements
  - template file contains reusable conclusion/report template
- If output is wrong/incomplete:
  - modify `scripts/parse_lp_input.py`
  - rerun command
  - repeat until outputs are correct

## Verification
- [ ] Script exists at `skills/parse-lp-input/scripts/parse_lp_input.py`.
- [ ] Running script generates all 6 output files.
- [ ] All objective variables appear in `variables`.
- [ ] All constraint term variables appear in `variables`.
- [ ] All parameter variables are explicitly listed in `variables`.
- [ ] Variable extraction follows source granularity (no unnecessary expansion).
- [ ] `variable_name_map_cn` covers every variable in `model_json.variables`.
- [ ] `problem_description_md` is consistent with `model_json`.
- [ ] `report_requirements_md` includes extracted report requirements.
- [ ] `report_template_md` includes an executable writing template.

## Anti-Patterns
- Do not manually hand-edit generated output as the primary workflow; fix script and rerun.
- Do not invent unsupported constraints/objectives.
- Do not skip parser rerun after script modifications.
- Do not output variables without Chinese mapping.

## Extension Points
- Add parsers for additional source formats (native CSV/Excel readers).
- Add confidence scores and extraction diagnostics.
- Add strict JSON schema validation for downstream solver/report skills.
