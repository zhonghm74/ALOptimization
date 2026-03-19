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
4. `skills/run-alm-lp-pipeline` - orchestrate the full flow

### Example input

- `examples/input/alm_lp_input.json`

### Run the full pipeline

```bash
python skills/run-alm-lp-pipeline/scripts/run_pipeline.py \
  --input examples/input/alm_lp_input.json \
  --output-dir examples/output
```

### Output files

- `examples/output/normalized_lp.json`
- `examples/output/solution.json`
- `examples/output/report.json`
- `examples/output/report.md`
