---
name: build-and-solve-lp
description: Build and solve LP models by dynamically creating and running a Python OR-Tools script.
license: MIT
---

# build-and-solve-lp

## Purpose
Use OR-Tools to construct and solve a linear programming (LP) model from normalized inputs, by dynamically creating a Python script under `scripts/`, then returning solver-ready results with strict quality checks.

## Triggers
- `solve alm lp model`
- `run ortools glop optimization`
- `build solver model from normalized json via dynamic script`
- `compute duals and reduced costs`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| Input.model_json | object | Normalized LP model with `variables`, `constraints`, `objective`, `metadata` |
| Input.solver_backend | string | OR-Tools backend, e.g. `GLOP`, `PDLP` |
| Input.command | shell | Dynamically create solver script under `scripts/`, then run: `python3 scripts/<generated_solver_script>.py --input <model_json> --backend <backend> --output <solution_json>` |
| Output.solution_json | object | Solver output with status, objective value, variable assignments, constraint activity |
| Output.status | string | `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNBOUNDED`, `ABNORMAL`, etc. |
| Output.variable_values | object | Primal variable assignments when a primal solution exists |
| Output.constraints | array | Constraint diagnostics: `name`, `lb`, `ub`, `activity`, `satisfied` |
| Output.duals | object | Dual values when backend and status support dual extraction |
| Output.reduced_costs | object | Reduced costs when backend and status support extraction |
| Output.validation | object | Verification results against modeling and numerical quality standards |

## Scripts
- No fixed solver script is checked in as the default implementation.
- For each task, dynamically create a temporary solver script under `scripts/`, execute it, validate outputs, and iterate if needed.
- Recommended temporary names:
  - `scripts/generated_build_and_solve_lp_<timestamp>.py`
  - `scripts/tmp_build_and_solve_lp.py`

## Script Lifecycle Policy
- Keep generated solver script after execution (do not delete by default).
- Preferred reusable path: `scripts/build_and_solve_lp.py` (or a stable configured path).
- Reuse-first decision:
  1. If script exists, run health checks first.
  2. Reuse only when all health checks pass.
  3. If script missing or health checks fail, regenerate/repair script, then rerun checks.
- Health checks must include:
  - **Requirement-fit check**: script matches current solve requirements (backend, model granularity, expected diagnostics).
  - **Output validation**: produced `solution_json` is structurally complete and numerically sane.
  - **Skill verification**: this skill's Verification checklist passes end-to-end.

## Process

### Phase 1 - Reuse or (Re)Create Solver Script
- If a reusable solver script exists in `scripts/`, run health checks first.
- If health checks pass, reuse script directly.
- If health checks fail or script is missing, create/repair solver script in `scripts/`.
- Script responsibilities:
  1. load normalized `model_json`
  2. build OR-Tools model (`variables`, `constraints`, `objective`)
  3. solve with selected backend (`GLOP`/`PDLP`)
  4. compute diagnostics (`activity`, `satisfied`, optional `duals`, `reduced_costs`)
  5. write `solution_json`

### Phase 2 - Run Solver Script
- Run generated script, e.g.:
  - `python3 scripts/<generated_solver_script>.py --input examples/alm_lp_full_test_input_parsed.json --backend GLOP --output examples/output/linear-programming-solver/solution.json`
- Ensure solver status is explicit and machine-readable.

### Phase 3 - Validate and Iterate Until Correct
- Validate:
  - current script matches current problem requirements (requirement-fit)
  - model references complete (`terms.var` all declared)
  - bounds/coefs numeric and valid
  - status interpretable
  - when primal exists, `objective_value` and `variable_values` present
  - constraint activities and satisfaction checks consistent
  - all `Verification Checklist` items pass
- If output is wrong/incomplete:
  - modify/regenerate temporary script
  - rerun
  - repeat until outputs are correct

## OR-Tools 建模过程（详细）

### Phase 1 - 模型输入检查（建模前）
1. **结构检查**  
   - 必须包含 `variables`、`constraints`、`objective`。  
   - 变量名唯一；约束名唯一；目标方向必须为 `max` 或 `min`。
2. **数值检查**  
   - 所有 `coef` 必须可转为浮点数。  
   - 变量上下界允许 `null`（对应无穷边界），否则必须是有效数值。
3. **引用完整性检查**  
   - 约束项 `terms[*].var` 与目标项 `terms[*].var` 必须全部出现在 `variables` 中。

### Phase 2 - OR-Tools 对象构建
1. **创建求解器**  
   - 使用 `pywraplp.Solver.CreateSolver(<backend>)` 创建求解器实例。  
   - 常见：`GLOP`（线性规划单纯形）、`PDLP`（大规模一阶法）。
2. **创建变量**  
   - 对每个变量 `v` 调用 `NumVar(lb, ub, name)`。  
   - `null` 下界映射为 `-infinity`，`null` 上界映射为 `+infinity`。
3. **创建约束**  
   - 对每个约束 `c` 调用 `Constraint(lb, ub, name)`。  
   - 对约束项 `coef * var` 调用 `SetCoefficient(variable_obj, coef)`。
4. **创建目标函数**  
   - 对每个目标项调用 `objective.SetCoefficient(variable_obj, coef)`。  
   - 根据 `sense` 调用 `SetMaximization()` 或 `SetMinimization()`。

### Phase 3 - 求解与状态解释
1. 调用 `solver.Solve()` 获取状态码。  
2. 映射为可读状态：`OPTIMAL` / `FEASIBLE` / `INFEASIBLE` / `UNBOUNDED` 等。  
3. 仅在存在原始可行解时输出 `variable_values` 和 `objective_value`。  
4. 在支持条件下输出 `duals`、`reduced_costs`、`iterations`、`wall_time_ms`。

### Phase 4 - 结果回填与一致性计算
1. **约束活动值**  
   - 计算 `activity = Σ(coef_i * x_i)` 并与 `lb/ub` 比较。  
2. **约束满足性**  
   - 按容差（建议 `1e-7`）判断 `lb <= activity <= ub`。  
3. **目标一致性**  
   - 复核目标值与变量解代入值是否一致（考虑常数项 `constant`）。

## 验证标准（Verification Standards）

| 维度 | 验证标准 | 通过条件 |
|---|---|---|
| 模型结构完整性 | 必要字段齐全，字段类型正确 | `variables/constraints/objective` 均存在且格式合法 |
| 变量引用一致性 | 目标与约束中变量均已声明 | 0 个未声明变量 |
| 边界有效性 | 变量/约束边界合法 | `lb <= ub`（若均非空）且均为数值或空 |
| 线性性 | 仅包含线性项 | 不出现变量乘变量、非线性函数项 |
| 可求解性 | OR-Tools 可成功建模并返回状态 | 非建模异常；返回有效状态码 |
| 原始可行性 | 解满足全部硬约束 | 所有硬约束 `satisfied=true`（容差内） |
| 软约束可解释性 | 松弛变量行为合理 | 松弛变量仅在约束冲突时非零 |
| 数值稳定性 | 求解结果无明显数值异常 | 不出现 NaN/Inf；活动值可计算 |
| 结果可复核性 | 可通过回代复核目标和约束 | 回代偏差在容差内 |

## Verification Checklist
- [ ] Solver script is dynamically created under `scripts/` and executed successfully.
- [ ] 所有目标项变量均在 `variables` 中声明。
- [ ] 所有约束项变量均在 `variables` 中声明。
- [ ] 所有约束均至少包含一个线性项，且至少有一侧边界（`lb` 或 `ub`）。
- [ ] OR-Tools 求解状态可解释（非未知状态字符串）。
- [ ] 若状态为 `OPTIMAL/FEASIBLE`，则必须输出 `objective_value` 与 `variable_values`。
- [ ] 约束活动值可计算，且满足性判断在容差范围内一致。

## Anti-Patterns
- Do not rely on a stale fixed solver script when dynamic generation is required.
- Do not reuse an existing solver script without checking current requirement-fit.
- Do not manually patch `solution_json` as primary workflow; fix generated script and rerun.
- Do not output variable assignments when solver has no primal solution.
- Do not assume dual/reduced-cost is always available for every backend/status.
- Do not skip reference checks between `terms.var` and declared variables.
- Do not silently coerce non-numeric coefficients/bounds.

## References
- `references/ortools_modeling_guide.md` - OR-Tools 建模与验证说明（本 skill 的规范参考文档）。

## Extension Points
- Add automatic backend selection policy based on model scale (`GLOP` vs `PDLP`).
- Add IIS/冲突诊断流程 for infeasible models.
- Add LP/MPS export pipeline for debugging and model audit.
