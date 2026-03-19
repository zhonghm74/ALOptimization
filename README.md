# ALOptimization
Create a Asset Liability Optimizer by Agent framework

## Environment setup

This repository now includes a Python development environment scaffold.

### 1) Create the environment

```bash
./scripts/create_env.sh
```

This script will:
- create a virtual environment at `.venv`
- install dependencies from `requirements.txt`
- create `.env` from `.env.example` (if `.env` does not exist yet)

### 2) Activate the environment

```bash
source .venv/bin/activate
```

### 3) Deactivate when done

```bash
deactivate
```

## Minimal ALM LP skills (quick end-to-end flow)

This repository now includes a simplified 4-skill LP workflow where constraints and objective
are fully defined in the input file.

### Skill list

1. `skills/parse-lp-input` - validate and normalize input JSON
2. `skills/build-and-solve-lp` - build and solve LP model with OR-Tools
3. `skills/generate-lp-report` - generate JSON and Markdown report
4. `skills/linear-programming-solver` - end-to-end methodology: parse -> build/solve -> report

### Example input

- `examples/alm_lp_full_test_input.md`

### End-to-end methodology flow

```text
Step 1: Use skills/parse-lp-input to extract model_json + problem_description_md + variable_name_map_cn
Step 2: Use skills/build-and-solve-lp methodology to model/solve with OR-Tools
Step 3: Use skills/generate-lp-report to produce report_json/report_md and charts
Step 4: Use skills/linear-programming-solver as orchestration methodology and quality checklist
```

### Output files

- `examples/output/normalized_lp.json`
- `examples/output/solution.json`
- `examples/output/report.json`
- `examples/output/report.md`
