---
name: linear-programming-solver
description: End-to-end LP methodology from parse_lp_input to OR-Tools solve and final reporting.
license: MIT
---

# linear-programming-solver

## Purpose
Define a complete, reproducible LP solution methodology that links three skills in sequence:
1) `parse-lp-input` (extract/normalize model),
2) `build-and-solve-lp` (OR-Tools modeling and solve),
3) `generate-lp-report` (result interpretation and visualization-ready reporting).

## Triggers
- `run full linear programming workflow`
- `parse build solve report end to end`
- `orchestrate parse_lp_input to final report`
- `methodology for lp optimization delivery`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| Input.source_documents | any | Markdown/TXT/PDF/CSV/Excel/业务规则文档等 |
| Stage1.model_json | object | parse_lp_input 输出的结构化 LP 模型 |
| Stage1.problem_description_md | markdown | 问题文字描述 |
| Stage1.variable_name_map_cn | object | 变量英文名到中文名映射 |
| Stage2.solution_json | object | OR-Tools 求解结果（status/objective/variables/constraints） |
| Stage3.report_json | object | 结构化结果报告（可用于系统集成） |
| Stage3.report_md | markdown | 面向业务和管理层的可读报告 |
| Stage3.chart_manifest | object | 图表索引与来源表关系（用于可视化追踪） |

## End-to-End Methodology

### Phase 1 - Parse (parse_lp_input)
目标：从业务文档抽取可求解 LP 定义并建立语义可解释层。  
执行要点：
1. 识别优化目标、决策变量、参数变量、约束条件及边界。
2. 生成 `model_json`（`variables/constraints/objective/metadata`）。
3. 生成 `problem_description_md`（问题背景、建模假设、口径说明）。
4. 生成 `variable_name_map_cn`，确保 `model_json.variables` 中所有变量均有中文名称。
5. 若模型为索引化表示（如 `x[t,Ai]`），保留索引语义，不做不必要展开。

阶段通过标准：
- 所有约束和目标引用变量均已声明；
- 参数变量完整列举；
- 变量中文映射覆盖率 100%。

### Phase 2 - Build & Solve (build-and-solve-lp)
目标：用 OR-Tools 将 `model_json` 转为可求解 LP 并获取稳定求解结果。  
执行要点：
1. 按 `build-and-solve-lp` 的 OR-Tools 建模规范创建变量、约束和目标。
2. 选择求解后端（默认 `GLOP`，大规模可评估 `PDLP`）。
3. 执行求解并输出 `solution_json`：
   - `status`、`objective_value`
   - `variable_values`
   - `constraints`（活动值与边界）
   - 可用时输出 `duals` 与 `reduced_costs`
4. 做求解结果一致性检查（约束容差、目标回代、NaN/Inf 检查）。

阶段通过标准：
- 状态可解释（`OPTIMAL/FEASIBLE/INFEASIBLE/...`）；
- 若存在原始可行解，变量赋值与目标值完整；
- 约束满足性判断与活动值一致。

### Phase 3 - Generate Report (generate-lp-report)
目标：把求解结果转化为可决策的结构化+可读报告，并可视化展示关键结果。  
执行要点：
1. 汇总核心指标：目标值、非零变量、约束满足情况、风险提示。
2. 输出 `report_json` 和 `report_md`，保证口径一致。
3. 构建 `report_tables` 与 `chart_manifest`，并调用可视化 skills 生成图表：
   - `scientific-visualization` / `matplotlib` / `seaborn` / `plotly`
4. 报告中同时提供：
   - 表格结果（可复核）
   - 图表结果（可读性）
   - 结论与建议（可执行）

阶段通过标准：
- 报告摘要、变量分析、约束分析完整；
- 图表均可追溯到 `report_tables`；
- 结论与数值不冲突。

## Verification Checklist
- [ ] 三阶段产物齐全：`model_json`、`solution_json`、`report_json/report_md`。
- [ ] Stage1 与 Stage2 变量命名一致，无未知变量引用。
- [ ] Stage2 约束满足性与容差判定一致，目标值可回代复核。
- [ ] Stage3 报告中的表格、图表、结论口径一致。
- [ ] 全流程保留关键假设与异常告警，便于审计与复现。

## Anti-Patterns
- Do not skip parse-stage semantic checks and directly solve incomplete models.
- Do not run solve-stage when Stage1 artifacts are inconsistent or missing.
- Do not produce narrative conclusions that are not supported by report tables/charts.
- Do not merge multiple scenario results without explicit scenario labeling.

## References
- `skills/parse-lp-input/SKILL.md`
- `skills/build-and-solve-lp/SKILL.md`
- `skills/build-and-solve-lp/references/ortools_modeling_guide.md`
- `skills/generate-lp-report/SKILL.md`
