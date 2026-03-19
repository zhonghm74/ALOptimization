---
name: generate-lp-report
description: Generate a complete LP optimization result report from model and solver artifacts.
license: MIT
---

# generate-lp-report

## Purpose
Produce decision-ready LP result reports that explain optimization outcomes, constraint behavior, and business implications in both machine-readable and human-readable formats.

## Triggers
- `generate lp optimization report`
- `summarize solver output for stakeholders`
- `write markdown report from lp result`
- `analyze constraint feasibility and sensitivity`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| Input.model_json | object/path | Normalized LP model definition |
| Input.solution_json | object/path | Solver output with status, objective, variable values, constraint activities |
| Output.report_json | object | Structured report payload for downstream systems |
| Output.report_md | markdown | Narrative report for human review |
| Output.summary | object | Key metrics (status, objective, counts, warnings) |
| Output.constraint_analysis | array | Per-constraint feasibility diagnostics |
| Output.variable_analysis | array | Ranked non-zero variables and contribution interpretation |

## Report Generation Method (Detailed)

### Phase 1 - Artifact Intake and Integrity Validation
1. Validate that model and solution artifacts are parseable JSON objects.
2. Verify required fields exist:
   - Model: `variables`, `constraints`, `objective`
   - Solution: `status`, `objective_value` (when applicable), `variable_values`, `constraints`
3. Check schema compatibility:
   - Variable names in `solution.variable_values` must exist in `model.variables`.
   - Constraint names in solution diagnostics must map to model constraints.
4. Emit explicit validation errors (do not silently continue on malformed artifacts).

### Phase 2 - Core Metrics Construction
1. Build top-level summary:
   - solver status
   - objective value
   - variable/constraint counts
   - non-zero variable count
2. Build variable analysis:
   - filter non-zero variables with tolerance (e.g., `1e-9`)
   - rank by absolute magnitude
   - optionally tag variable groups (decision/slack/parameter) when metadata is available
3. Build constraint analysis:
   - compute/collect `activity`, `lb`, `ub`
   - evaluate feasibility with tolerance (e.g., `1e-7`)
   - classify each constraint as binding / non-binding / violated

### Phase 3 - Business Interpretation Layer
1. Explain objective result in business terms:
   - what does objective magnitude represent
   - compare with baseline (if provided)
2. Explain major driver variables:
   - largest absolute allocations
   - largest contributors to objective
3. Explain risk/compliance implications:
   - any violated or near-binding constraints
   - slack-variable usage and penalty interpretation

### Phase 4 - Output Rendering
1. `report_json` should include:
   - `metadata`
   - `summary`
   - `variable_analysis`
   - `constraint_analysis`
   - `duals` / `reduced_costs` when available
2. `report_md` should include:
   - Executive summary
   - Optimization status and objective
   - Top variable table
   - Constraint satisfaction table
   - Interpretation and recommendations
3. Keep ordering deterministic for reproducibility.

## Verification Standards

| Dimension | Standard | Pass Criteria |
|---|---|---|
| Input integrity | Model/solution artifacts are valid and compatible | No missing required fields; no unknown variable references |
| Numeric sanity | Report values are finite and consistent | No NaN/Inf in objective/activity tables |
| Constraint correctness | Feasibility judgment is tolerance-aware | `satisfied` flags align with bounds and activities |
| Determinism | Repeated runs produce same ordering | Stable sort rules for variables/constraints |
| Completeness | Required report sections are present | JSON + Markdown both include summary and diagnostics |
| Interpretability | Business-readable narrative exists | Markdown contains objective interpretation and key findings |

## Verification Checklist
- [ ] `report_json` and `report_md` are both generated.
- [ ] Markdown report includes status, objective, top variables, and constraint table.
- [ ] Every reported non-zero variable exists in model definition.
- [ ] Every constraint diagnostic contains `name`, `lb`, `ub`, `activity`, `satisfied`.
- [ ] Violations and warnings are explicitly surfaced.

## Anti-Patterns
- Do not mark a constraint as satisfied when activity is missing.
- Do not hide infeasible/abnormal solver statuses in narrative text.
- Do not output unsorted variable rankings with unstable order.
- Do not drop slack-variable interpretation when soft constraints are present.

## Extension Points
- Add scenario-vs-scenario comparison sections.
- Add chart references for dashboard/BI rendering.
- Add automated narrative templates for executive vs. quant audiences.
