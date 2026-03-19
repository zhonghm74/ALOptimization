---
name: generate-lp-report
description: Generate LP optimization reports by dynamically creating and running a Python reporting script.
license: MIT
---

# generate-lp-report

## Purpose
Produce decision-ready LP result reports that explain optimization outcomes, constraint behavior, and business implications in both machine-readable and human-readable formats, using dynamically generated scripts under `scripts/`.

## Triggers
- `generate lp optimization report`
- `summarize solver output for stakeholders`
- `write markdown report from lp result via dynamic script`
- `analyze constraint feasibility and sensitivity`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| Input.model_json | object/path | Normalized LP model definition |
| Input.solution_json | object/path | Solver output with status, objective, variable values, constraint activities |
| Input.report_requirements_md | markdown/path | **Required** report requirements extracted by `parse-lp-input` (e.g. `<stem>_report_requirements.md`) |
| Input.report_template_md | markdown/path | Optional report template extracted by `parse-lp-input` (e.g. `<stem>_report_template.md`) |
| Input.command | shell | Dynamically create reporting script under `scripts/`, then run: `python3 scripts/<generated_report_script>.py --model <model_json> --solution <solution_json> --requirements <report_requirements_md> --template <report_template_md> --output-dir <dir>` |
| Output.report_json | object | Structured report payload for downstream systems |
| Output.report_md | markdown | Narrative report for human review |
| Output.summary | object | Key metrics (status, objective, counts, warnings) |
| Output.constraint_analysis | array | Per-constraint feasibility diagnostics |
| Output.variable_analysis | array | Ranked non-zero variables and contribution interpretation |
| Output.report_tables | object | Canonical table blocks used by both markdown report and chart inputs |
| Output.chart_manifest | object | Chart list with file paths, metric definitions, and source table references |
| Output.chart_files | array | Generated chart files (`.png` / `.svg` / `.html`) |

## Scripts
- No fixed reporting script is checked in as default implementation.
- For each reporting task:
  1. Dynamically create a temporary Python script in `scripts/`
  2. Run script to generate report outputs
  3. Validate results and iterate script until outputs are correct
- Recommended temporary names:
  - `scripts/generated_generate_lp_report_<timestamp>.py`
  - `scripts/tmp_generate_lp_report.py`

## Process

### Phase 1 - Dynamically Create Report Script
- Dynamically create a Python script in `scripts/` that:
  - reads `model_json` and `solution_json`
  - reads `report_requirements_md` (required) and `report_template_md` (optional)
  - builds `summary`, `variable_analysis`, `constraint_analysis`
  - builds `report_tables`
  - generates `report_json` and `report_md` in strict alignment with report requirements
  - (optionally) generates chart files and `chart_manifest`

### Phase 2 - Run Script and Generate Outputs
- Run generated script, e.g.:
  - `python3 scripts/<generated_report_script>.py --model examples/output/linear-programming-solver/normalized_lp.json --solution examples/output/linear-programming-solver/solution.json --requirements examples/alm_lp_full_test_input_report_requirements.md --template examples/alm_lp_full_test_input_report_template.md --output-dir examples/output/linear-programming-solver`
- Ensure outputs are written and parseable.

### Phase 3 - Validate and Iterate Until Correct
- Validate:
  - required outputs exist (`report_json`, `report_md`)
  - required inputs were consumed (`report_requirements_md` must be loaded successfully)
  - fields are complete and internally consistent
  - report sections/charts satisfy requirement checklist from `report_requirements_md`
  - chart entries map to `report_tables` (if charts generated)
- If output is wrong/incomplete:
  - modify/regenerate temporary script
  - rerun
  - repeat until correct

## Report Generation Method (Detailed)

### Phase 1 - Artifact Intake and Integrity Validation
1. Validate that model and solution artifacts are parseable JSON objects.
2. Validate `report_requirements_md` is present and parseable markdown text.
3. If `report_template_md` is provided, validate it is readable and can be embedded/reused.
4. Verify required fields exist:
   - Model: `variables`, `constraints`, `objective`
   - Solution: `status`, `objective_value` (when applicable), `variable_values`, `constraints`
5. Check schema compatibility:
   - Variable names in `solution.variable_values` must exist in `model.variables`.
   - Constraint names in solution diagnostics must map to model constraints.
6. Emit explicit validation errors (do not silently continue on malformed artifacts).

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
   - `requirements_trace` (report requirements source and satisfaction flags)
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
   - requirement-driven sections required by `report_requirements_md`
3. Keep ordering deterministic for reproducibility.

## Visualization (Cross-Skill Orchestration)

在输出表格的同时，`generate-lp-report` 应调用其他可视化 skills 生成图表，并将图表嵌入最终报告。

### A. Visualization Data Contract
1. 先生成标准表格层（`report_tables`），作为唯一数据源：
   - `table_top_variables`
   - `table_constraint_status`
   - `table_daily_pnl`（若模型包含时间索引）
   - `table_cumulative_pnl`（若可计算）
2. 图表必须引用 `report_tables`，避免“图表与表格口径不一致”。

### B. Recommended Chart Types
- **变量贡献图**：Top N 非零变量条形图（`table_top_variables`）
- **约束状态图**：约束余量/紧绑定分布图（`table_constraint_status`）
- **累计收益图**：累计净收益折线图（`table_cumulative_pnl`）
- **每日收益图**：每日净收益柱状图 + 滚动均值（`table_daily_pnl`）

### C. Skill Collaboration Rules
- Publication-grade static charts：优先调用 `scientific-visualization` 或 `matplotlib`
- Statistical quick plots：可调用 `seaborn`
- Interactive charts/dashboard：可调用 `plotly`
- 报告中必须记录图表来源 skill、输入表名、输出文件路径（写入 `chart_manifest`）

### D. Report Embedding Rules
- `report_md` 在对应分析段落下插入图表（图片或交互链接）
- 每个图表要有：
  - 图表标题
  - 指标定义与口径说明
  - 与表格字段的一致性说明（引用 `report_tables` 字段名）

## Verification Standards

| Dimension | Standard | Pass Criteria |
|---|---|---|
| Input integrity | Model/solution/requirements artifacts are valid and compatible | No missing required fields; no unknown variable references; requirements file readable |
| Numeric sanity | Report values are finite and consistent | No NaN/Inf in objective/activity tables |
| Constraint correctness | Feasibility judgment is tolerance-aware | `satisfied` flags align with bounds and activities |
| Determinism | Repeated runs produce same ordering | Stable sort rules for variables/constraints |
| Completeness | Required report sections are present | JSON + Markdown both include summary and diagnostics |
| Interpretability | Business-readable narrative exists | Markdown contains objective interpretation and key findings |
| Table-chart consistency | Charts use the same underlying report tables | Every chart can be traced to `report_tables` entry |
| Visualization completeness | Required charts are produced when data is available | `chart_manifest` non-empty and files exist |
| Requirement compliance | Report follows parser-extracted requirement checklist | Required sections/charts all present or explicitly marked unavailable with reason |

## Verification Checklist
- [ ] Reporting script is dynamically created under `scripts/` and executed successfully.
- [ ] `report_requirements_md` (from `parse-lp-input`) is provided and successfully parsed.
- [ ] `report_json` and `report_md` are both generated.
- [ ] Markdown report includes status, objective, top variables, and constraint table.
- [ ] Every reported non-zero variable exists in model definition.
- [ ] Every constraint diagnostic contains `name`, `lb`, `ub`, `activity`, `satisfied`.
- [ ] Violations and warnings are explicitly surfaced.
- [ ] `report_tables` exists and chart inputs are derived from these tables only.
- [ ] `chart_manifest` lists chart type, source table, output path, and generating skill.
- [ ] Charts embedded in `report_md` are accessible and correspond to report tables.
- [ ] Report covers mandatory sections/charts defined in `report_requirements_md`.

## Anti-Patterns
- Do not rely on stale fixed report scripts when dynamic generation is required.
- Do not manually patch `report_json`/`report_md` as primary workflow; fix generated script and rerun.
- Do not ignore parser-extracted `report_requirements_md` when composing report sections/charts.
- Do not mark a constraint as satisfied when activity is missing.
- Do not hide infeasible/abnormal solver statuses in narrative text.
- Do not output unsorted variable rankings with unstable order.
- Do not drop slack-variable interpretation when soft constraints are present.
- Do not generate charts from ad-hoc transformed data that is absent from `report_tables`.
- Do not present chart conclusions that contradict table values.

## Extension Points
- Add scenario-vs-scenario comparison sections.
- Add chart references for dashboard/BI rendering.
- Add automated narrative templates for executive vs. quant audiences.
- Add auto-selection policy for chart skill (`matplotlib` vs `seaborn` vs `plotly`) by audience and output format.
