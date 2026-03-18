---
name: run-alm-lp-pipeline
description: Orchestrate a minimal end-to-end ALM LP flow from raw input to optimization report.
---

# run-alm-lp-pipeline

## Purpose
Run the full minimal pipeline:
1. parse input
2. build and solve LP
3. generate report

## Input
- raw LP input JSON
- output directory

## Output
- `normalized_lp.json`
- `solution.json`
- `report.json`
- `report.md`

## Script
Use:

```bash
python skills/run-alm-lp-pipeline/scripts/run_pipeline.py \
  --input examples/input/alm_lp_input.json \
  --output-dir examples/output
```
