# OR-Tools 线性规划建模与验证说明（build-and-solve-lp）

## 1. 目标
本文档定义 `build-and-solve-lp` 在 OR-Tools 下的标准建模流程、状态解释和结果验证标准，用于保证不同模型来源下的求解质量一致性。

## 2. 推荐求解框架
- Python API：`ortools.linear_solver.pywraplp`
- 典型后端：
  - `GLOP`：通用 LP 求解（默认推荐）
  - `PDLP`：大规模 LP 场景可选

## 3. 输入模型规范（建议）
- `variables`: `[{name, lb, ub}]`
- `constraints`: `[{name, lb, ub, terms:[{var, coef}]}]`
- `objective`: `{sense, terms:[{var, coef}], constant}`
- `metadata`: 可选

约定：
- `lb`/`ub` 可为 `null`（表示无界）
- `sense` 仅允许 `max` / `min`
- `name` 应唯一（变量名、约束名分别唯一）

## 4. OR-Tools 建模步骤

### Step 1 - 创建求解器
```python
solver = pywraplp.Solver.CreateSolver("GLOP")
```
若返回 `None`，说明后端不可用或环境异常，需立即失败。

### Step 2 - 创建变量
```python
v = solver.NumVar(lb, ub, name)
```
- `lb=None` 映射 `-solver.infinity()`
- `ub=None` 映射 `+solver.infinity()`

### Step 3 - 创建约束
```python
ct = solver.Constraint(lb, ub, name)
ct.SetCoefficient(var_obj, coef)
```
- 每个约束应至少有一个 term
- 至少存在一个边界（`lb` 或 `ub`）

### Step 4 - 创建目标函数
```python
obj = solver.Objective()
obj.SetCoefficient(var_obj, coef)
obj.SetMaximization()  # or SetMinimization()
```

### Step 5 - 求解并读取结果
```python
status_code = solver.Solve()
```
- `OPTIMAL` / `FEASIBLE`：可读取原始解
- 其他状态：不应输出伪造变量取值

## 5. 状态与输出建议
- 输出字段：
  - `status`
  - `objective_value`（仅当有原始可行解）
  - `variable_values`
  - `constraints[{name, lb, ub, activity}]`
  - `duals`（可用时）
  - `reduced_costs`（可用时）
  - `iterations`, `wall_time_ms`

## 6. 结果验证标准

### 6.1 结构验证
- 必要字段齐全
- 系数、边界可数值化
- 所有 `terms.var` 均可在变量表中找到

### 6.2 数学验证
- 对每个约束计算活动值：
  - `activity = Σ(coef_i * x_i)`
- 满足性判定（容差 `1e-7`）：
  - `lb is None or activity >= lb - tol`
  - `ub is None or activity <= ub + tol`

### 6.3 目标复核
- 回代复核：
  - `recomputed_obj = Σ(coef_i * x_i) + constant`
- 与求解器目标值偏差应小于容差（例如 `1e-6`）

### 6.4 软约束解释性
- 若存在松弛变量，需确认：
  - 非负约束是否满足
  - 非零松弛是否与对应约束紧张程度一致

## 7. 常见问题与处理
- **INFEASIBLE**：检查边界冲突、单位混淆、过紧比例约束
- **UNBOUNDED**：检查目标方向与关键变量上界是否缺失
- **ABNORMAL / NOT_SOLVED**：检查后端可用性与输入数值稳定性

## 8. 最佳实践
- 为每个约束命名可读 `name`
- 保留 `metadata.assumptions`
- 对关键比例约束做显式线性化（避免隐式非线性）
- 对跨期模型统一索引命名规则（如 `x_D01_A01`）
