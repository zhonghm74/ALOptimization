---
name: visualize-tabular-data
description: Generate practical charts and a markdown visual report from CSV/JSON/Excel tabular datasets.
license: MIT
---

# visualize-tabular-data

## Purpose
Create quick, decision-ready visualizations from tabular data files and save a reproducible chart report.

## Triggers
- `visualize csv data`
- `generate eda charts from json`
- `plot tabular dataset automatically`
- `build markdown chart report`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| input_path | path | CSV / JSON / XLSX dataset file |
| output_dir | path | Directory for chart PNGs + report files |
| max_numeric_plots | int | Maximum number of numeric charts (default `6`) |
| max_categorical_plots | int | Maximum number of categorical charts (default `3`) |
| output.summary_json | path | JSON summary of generated plots |
| output.report_md | path | Markdown report referencing generated PNG files |

## Process

### Phase 1 - Load and Profile Data
- Read input dataset into a DataFrame.
- Detect numeric, categorical, and datetime-like columns.

### Phase 2 - Generate Charts
- Create line charts for datetime + numeric combinations when possible.
- Create histograms for numeric columns.
- Create top-category bar charts for categorical columns.
- Create correlation heatmap when at least two numeric columns exist.

### Phase 3 - Emit Report Artifacts
- Save generated charts as PNG files.
- Write markdown report and JSON summary to output directory.

## Scripts

### generate_visual_report.py
Path: `skills/visualize-tabular-data/scripts/generate_visual_report.py`

Usage:

```bash
python skills/visualize-tabular-data/scripts/generate_visual_report.py \
  --input examples/alm_lp_full_test_input_parsed.json \
  --output-dir examples/output/visual_report
```

Exit Codes:
- `0`: Success.
- `1`: Unexpected runtime failure.
- `2`: Invalid input path/format or empty/unusable dataset.

## Verification
- [ ] Script succeeds with CSV/JSON/XLSX input and writes report artifacts.
- [ ] At least one chart is generated when numeric or categorical data exists.
- [ ] Empty or unsupported input fails with exit code `2`.
- [ ] Output markdown references only files that were actually generated.

## Anti-Patterns
- Do not silently skip all columns without emitting a reason in summary warnings.
- Do not overwrite unrelated output directories.
- Do not assume a datetime index exists.

## Extension Points
- Add pairplot/scatter-matrix generation for medium-width datasets.
- Add optional Plotly interactive HTML outputs.
- Add chart theming presets for executive vs. analyst audiences.
