---
name: parse-lp-input
description: Extract variables, constraints, and objective from JSON, Markdown, TXT, CSV, or Excel documents, then normalize into LP-ready JSON.
license: MIT
---

# parse-lp-input

## Purpose
Convert heterogeneous ALM input documents into a validated and normalized LP specification consumed by solver skills.

## Triggers
- `extract LP model from markdown or txt`
- `parse variables constraints objective from csv or excel`
- `normalize alm optimization input from any document`
- `prepare model spec for ortools`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| input_path | path | Input document path (`.json`, `.md`, `.txt`, `.csv`, `.xlsx`, `.xlsm`, `.xls`) |
| output_path | path | Normalized JSON output path |
| output.variables | array | Variables with normalized bounds (`float` or `null`) |
| output.constraints | array | Constraint list referencing declared variables only |
| output.objective | object | Objective with validated sense and numeric coefficients |

## Process

### Phase 1 - Structural Validation
- Detect source format and extract `variables`, `constraints`, `objective`.
- Support direct JSON, sectioned tabular CSV/Excel, and markdown/txt equation documents.

### Phase 2 - Numeric Normalization
- Normalize numeric values to float.
- Preserve `null` for open bounds.

### Phase 3 - Emission
- Write canonical normalized JSON used by downstream skills.

## Scripts

### parse_lp_input.py
Path: `skills/parse-lp-input/scripts/parse_lp_input.py`

Usage:

```bash
python skills/parse-lp-input/scripts/parse_lp_input.py \
  --input examples/alm_lp_full_test_input.md \
  --output examples/output/normalized_lp.json
```

Exit Codes:
- `0`: Success.
- `1`: Unexpected runtime failure.
- `2`: Input data validation error (schema/reference/bounds).

## Verification
- [ ] Valid input returns exit code `0` and writes `normalized_lp.json`.
- [ ] Markdown/TXT equation documents can be parsed into valid LP JSON.
- [ ] Sectioned CSV/Excel inputs can be parsed into valid LP JSON.
- [ ] Duplicate variable names fail with exit code `2`.
- [ ] Unknown variable references in objective/constraints fail with exit code `2`.

## Anti-Patterns
- Do not infer missing variables from terms.
- Do not silently coerce non-numeric coefficient values.
- Do not emit partial output after validation errors.

## Extension Points
- Add optional schema versioning and backward compatibility checks.
- Add domain-specific ALM business-rule prechecks before normalization.
- Add LLM-assisted extraction fallback for highly unstructured documents.
