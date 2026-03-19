---
name: run-alm-lp-pipeline
description: Orchestrate a minimal end-to-end ALM LP flow from raw input to optimization report.
license: MIT
---

# run-alm-lp-pipeline

## Purpose
Orchestrate the full minimal ALM LP flow from raw input to final report artifacts.

## Triggers
- `run alm lp pipeline end to end`
- `execute parse solve report workflow`
- `one command optimization pipeline`
- `produce normalized solution and report artifacts`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| input | path | Raw LP JSON input file |
| output_dir | path | Directory for generated artifacts |
| solver | string | Solver backend passed to solve stage |
| extracted_json | path | Optional AI-extracted LP JSON forwarded to parse step |
| output.normalized_lp.json | file | Normalized model input |
| output.solution.json | file | Solver result payload |
| output.report.json / report.md | file | User-facing reporting outputs |

## Process

### Phase 1 - Parse
- Run `parse-lp-input` script to validate and normalize data.

### Phase 2 - Solve
- Run `build-and-solve-lp` script with configured solver.

### Phase 3 - Report
- Run `generate-alm-report` script and emit final artifacts.

## Scripts

### run_pipeline.py
Path: `skills/run-alm-lp-pipeline/scripts/run_pipeline.py`

Usage:

```bash
python skills/run-alm-lp-pipeline/scripts/run_pipeline.py \
  --input examples/alm_lp_full_test_input.md \
  --extracted-json /tmp/ai_extracted_lp.json \
  --output-dir examples/output
```

Exit Codes:
- `0`: Success.
- `1`: Unexpected runtime failure.
- `2`: Upstream stage failed (parse/solve/report) or invalid arguments.

## Verification
- [ ] End-to-end run returns exit code `0` on valid input.
- [ ] When a stage fails, pipeline exits non-zero and surfaces failing command.
- [ ] Output directory contains all four target artifacts.

## Anti-Patterns
- Do not continue to downstream stages after an upstream failure.
- Do not swallow subprocess return codes.
- Do not hardcode input/output paths in orchestration logic.

## Extension Points
- Add optional stage-skipping flags (e.g., run report-only).
- Add batch execution over multiple scenario inputs.
