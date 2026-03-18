---
name: parse-lp-input
description: Validate and normalize an ALM linear programming input file when constraints and objective are provided by the user as data.
license: MIT
---

# parse-lp-input

## Purpose
Convert raw ALM LP JSON into a validated and normalized specification consumed by the solver skill.

## Triggers
- `validate LP input json`
- `normalize alm optimization input`
- `check variables constraints objective format`
- `prepare model spec for ortools`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| input_path | path | Raw JSON containing `variables`, `constraints`, `objective` |
| output_path | path | Normalized JSON output path |
| output.variables | array | Variables with normalized bounds (`float` or `null`) |
| output.constraints | array | Constraint list referencing declared variables only |
| output.objective | object | Objective with validated sense and numeric coefficients |

## Process

### Phase 1 - Structural Validation
- Require top-level `variables`, `constraints`, `objective`.
- Validate variable names, bound consistency, and term references.

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
  --input examples/input/alm_lp_input.json \
  --output examples/output/normalized_lp.json
```

Exit Codes:
- `0`: Success.
- `1`: Unexpected runtime failure.
- `2`: Input data validation error (schema/reference/bounds).

## Verification
- [ ] Valid input returns exit code `0` and writes `normalized_lp.json`.
- [ ] Duplicate variable names fail with exit code `2`.
- [ ] Unknown variable references in objective/constraints fail with exit code `2`.

## Anti-Patterns
- Do not infer missing variables from terms.
- Do not silently coerce non-numeric coefficient values.
- Do not emit partial output after validation errors.

## Extension Points
- Add optional schema versioning and backward compatibility checks.
- Add domain-specific ALM business-rule prechecks before normalization.
