---
name: visualize-optimization-results
description: Visualize LP solver outputs with variable contribution and constraint tightness charts.
license: MIT
---

# visualize-optimization-results

## Purpose
Turn LP solver outputs into readable diagnostics charts for decision review.

## Triggers
- `visualize optimization solution`
- `plot lp result diagnostics`
- `analyze constraint tightness`
- `chart top decision variables`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| solution_path | path | Solver JSON result (contains `status`, `variable_values`, `constraints`) |
| output_dir | path | Directory for charts and markdown/json report |
| top_n | int | Number of top non-zero variables to visualize (default `30`) |
| output.summary_json | path | Summary metrics and chart manifest |
| output.report_md | path | Markdown report with embedded charts |

## Process

### Phase 1 - Load Solver Result
- Validate required fields.
- Extract non-zero variables and constraint activity/bounds.

### Phase 2 - Build Diagnostics Charts
- Plot top non-zero variables by absolute magnitude.
- Plot constraint margin distribution.
- Plot tightest constraints (smallest margins).

### Phase 3 - Export Report
- Save chart images.
- Save markdown report and machine-readable summary JSON.

## Scripts

### plot_solution_diagnostics.py
Path: `skills/visualize-optimization-results/scripts/plot_solution_diagnostics.py`

Usage:

```bash
python skills/visualize-optimization-results/scripts/plot_solution_diagnostics.py \
  --solution examples/output/pipeline_from_compact_indexed/solution.json \
  --output-dir examples/output/solution_viz
```

Exit Codes:
- `0`: Success.
- `1`: Unexpected runtime failure.
- `2`: Invalid solver artifact format.

## Verification
- [ ] Script rejects missing `variable_values`/`constraints` with exit code `2`.
- [ ] Non-empty solver artifacts produce at least one chart.
- [ ] Markdown report references generated files only.
- [ ] Works for both optimal and feasible statuses.

## Anti-Patterns
- Do not treat zero-value variables as decision drivers.
- Do not ignore constraints with one-sided bounds when computing margins.
- Do not fail silently when no charts can be generated.

## Extension Points
- Add per-index aggregation for time-series solutions.
- Add sankey/stacked exposure visualizations by business group.
- Add threshold-based alert coloring for near-binding constraints.
