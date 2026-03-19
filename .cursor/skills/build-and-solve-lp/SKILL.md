---
name: build-and-solve-lp
description: Build and solve an ALM linear programming model in OR-Tools from a normalized input file.
license: MIT
---

# build-and-solve-lp

## Purpose
Build and solve an ALM LP model with OR-Tools `MPSolver` from normalized JSON input.

## Triggers
- `solve alm lp model`
- `run ortools glop optimization`
- `build solver model from normalized json`
- `compute duals and reduced costs`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| input_path | path | Normalized LP JSON |
| output_path | path | Solver result JSON |
| solver | string | Solver backend, default `GLOP` |
| output.status | string | Solver status (`OPTIMAL`, `INFEASIBLE`, etc.) |
| output.variable_values | object | Variable assignment map when a primal solution exists |
| output.constraints | array | Constraint bounds and activity values |
| output.duals/reduced_costs | object | LP sensitivity values when available |

## Process

### Phase 1 - Model Assembly
- Create variables and constraints from normalized spec.
- Build linear objective (max or min).

### Phase 2 - Solve
- Invoke OR-Tools backend (`GLOP` by default).
- Collect status, iterations, and wall time.

### Phase 3 - Post-processing
- Emit primal values (if feasible/optimal).
- Emit dual/reduced cost values when available.

## Scripts

### build_and_solve_lp.py
Path: `skills/build-and-solve-lp/scripts/build_and_solve_lp.py`

Usage:

```bash
python skills/build-and-solve-lp/scripts/build_and_solve_lp.py \
  --input examples/output/normalized_lp.json \
  --output examples/output/solution.json
```

Exit Codes:
- `0`: Success.
- `1`: Unexpected runtime failure.
- `2`: Invalid model input or unsupported solver configuration.

## Verification
- [ ] Valid normalized input returns exit code `0` and writes `solution.json`.
- [ ] Invalid/unknown solver returns exit code `2`.
- [ ] Output includes `status`, `constraints`, and timing metrics.

## Anti-Patterns
- Do not treat missing primal solution as valid variable assignments.
- Do not assume dual values are always available for all statuses/backends.
- Do not hide solver creation failures.

## Extension Points
- Add solver parameter tuning profile by scenario size.
- Add optional persistence of LP/MPS model exports for debugging.
