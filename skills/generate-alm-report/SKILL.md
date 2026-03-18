---
name: generate-alm-report
description: Generate a user-facing ALM optimization report from LP inputs and solver outputs.
license: MIT
---

# generate-alm-report

## Purpose
Generate concise machine-readable and human-readable reports from ALM LP solver outputs.

## Triggers
- `generate alm optimization report`
- `summarize lp solve result`
- `render markdown from solution json`
- `check constraint satisfaction report`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| normalized_input | path | Normalized LP specification JSON |
| solution | path | Solver output JSON |
| report_json | path | Structured report output |
| report_md | path | Markdown report output |
| output.constraint_checks | array | Constraint activity and satisfaction flags |
| output.non_zero_variables | array | Sorted non-zero decision variables |

## Process

### Phase 1 - Load and Validate Artifacts
- Load normalized model and solver output JSON.
- Validate expected report fields.

### Phase 2 - Aggregate Metrics
- Build summary counts and status metadata.
- Compute constraint satisfaction flags.

### Phase 3 - Render Outputs
- Write JSON report for programmatic consumption.
- Write Markdown report for user review.

## Scripts

### generate_alm_report.py
Path: `skills/generate-alm-report/scripts/generate_alm_report.py`

Usage:

```bash
python skills/generate-alm-report/scripts/generate_alm_report.py \
  --normalized-input examples/output/normalized_lp.json \
  --solution examples/output/solution.json \
  --report-json examples/output/report.json \
  --report-md examples/output/report.md
```

Exit Codes:
- `0`: Success.
- `1`: Unexpected runtime failure.
- `2`: Invalid input artifact format or missing required fields.

## Verification
- [ ] Valid inputs return exit code `0` and produce `report.json` + `report.md`.
- [ ] Invalid JSON input fails with exit code `2`.
- [ ] Markdown output includes summary and constraint table sections.

## Anti-Patterns
- Do not report constraints as satisfied when activity is missing.
- Do not reorder variables without deterministic sorting.
- Do not drop solver status in final report.

## Extension Points
- Add chart-friendly output blocks for BI dashboards.
- Add scenario comparison sections for stress test batches.
