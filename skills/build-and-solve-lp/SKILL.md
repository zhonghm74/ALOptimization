---
name: build-and-solve-lp
description: Build and solve an ALM linear programming model in OR-Tools from a normalized input file.
---

# build-and-solve-lp

## Purpose
Read a normalized LP spec and solve it with OR-Tools MPSolver (default: GLOP).

## Input
- `input_path`: normalized LP JSON.
- `output_path`: solution JSON.

## Output
- solver status
- objective value (if solved)
- variable values
- constraint activities
- optional dual values and reduced costs when available

## Script
Use:

```bash
python skills/build-and-solve-lp/scripts/build_and_solve_lp.py \
  --input examples/output/normalized_lp.json \
  --output examples/output/solution.json
```
