# AGENTS.md

## Cursor Cloud specific instructions

### Project overview
ALOptimization is a Python-based AI-agent skill framework for Asset-Liability Management (ALM) LP optimization. It has no running servers or services — it is a methodology/skill library consumed by AI coding agents. See `README.md` for the full skill list and end-to-end workflow.

### Environment
- Python 3.12+ virtual environment at `.venv`; activate with `source .venv/bin/activate`.
- Dependencies listed in `requirements.txt`; install via `pip install -r requirements.txt` inside the venv.
- `.env` is copied from `.env.example` on first setup (by `scripts/create_env.sh`).

### Gotcha: `python3.12-venv` system package
The base VM may not have `python3.12-venv` installed. The update script installs it automatically. If `python3 -m venv` fails, run `sudo apt-get install -y python3.12-venv`.

### Lint & test
- **Lint:** `ruff check .` and `black --check .` (pre-existing warnings exist in skill helper scripts under `skills/*/scripts/`).
- **Test:** `pytest` — the repo currently has no automated test files; pytest will exit with code 5 (no tests collected). This is expected.
- **Format:** `black .` to auto-format.

### Running the core pipeline
There is no long-running application or dev server. The product is used by writing and executing Python scripts that follow the skill methodology docs in `skills/`. A typical end-to-end flow:
1. Load or create a model JSON (see `examples/alm_lp_full_test_input_parsed.json`).
2. Build and solve with OR-Tools (`from ortools.linear_solver import pywraplp`).
3. Generate reports with pandas/matplotlib.

### Key packages
`ortools` (LP solver), `numpy`, `pandas`, `matplotlib`, `seaborn`, `plotly`, `pydantic`, `cvxpy`, `scipy`.
