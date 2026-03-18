---
name: generate-alm-report
description: Generate a user-facing ALM optimization report from LP inputs and solver outputs.
---

# generate-alm-report

## Purpose
Transform LP solution artifacts into a concise report for users.

## Input
- normalized LP JSON
- solver result JSON

## Output
- report JSON for machine consumption
- markdown report for human reading

## Script
Use:

```bash
python skills/generate-alm-report/scripts/generate_alm_report.py \
  --normalized-input examples/output/normalized_lp.json \
  --solution examples/output/solution.json \
  --report-json examples/output/report.json \
  --report-md examples/output/report.md
```
