# 资产负债管理（ALM）线性规划测试输入（完整样例）

## 1. 元数据

| 字段 | 值 |
|---|---|
| 案例编号 | `alm_full_test_001` |
| 案例名称 | ALM 完整测试输入（含数据/约束/目标） |
| 币种 | CNY |
| 规划周期（月） | 12 |
| 描述 | 用于 ALM LP 流程的完整测试样例，包含业务数据与可建模数据 |

---

## 2. 业务数据

### 2.1 资产池

| 资产ID | 资产名称 | 预期收益率 | 流动性权重 | 久期（年） | 下界 | 上界 |
|---|---|---:|---:|---:|---:|---:|
| `gov_bond` | 政府债券组合 | 0.038 | 0.95 | 2.0 | 0 | 120 |
| `corp_bond` | 企业债券组合 | 0.062 | 0.60 | 4.0 | 0 | 90 |
| `mortgage_loan` | 按揭贷款组合 | 0.075 | 0.20 | 6.0 | 40 | 100 |

### 2.2 负债池

| 负债ID | 负债名称 | 资金成本率 | 下界 | 上界 |
|---|---|---:|---:|---:|
| `deposit_funding` | 客户存款资金 | 0.018 | 110 | 220 |
| `wholesale_funding` | 同业/批发融资 | 0.041 | 0 | 80 |

### 2.3 策略参数

| 参数 | 数值 |
|---|---:|
| 总资产目标 | 200 |
| 最低流动性覆盖 | 120 |
| 久期暴露上限 | 850 |
| 批发融资上限 | 60 |
| 企业债集中度上限 | 70 |

---

## 3. 变量映射（业务语义）

| 变量名 | 含义 |
|---|---|
| `asset_gov_bond` | 政府债券组合配置金额 |
| `asset_corp_bond` | 企业债券组合配置金额 |
| `asset_mortgage_loan` | 按揭贷款组合配置金额 |
| `funding_deposit` | 存款来源融资金额 |
| `funding_wholesale` | 批发来源融资金额 |
| `liquidity_shortfall` | 流动性软约束松弛变量 |

---

## 4. 决策变量范围

| 变量 | 下界 | 上界 |
|---|---:|---:|
| `asset_gov_bond` | 0 | 120 |
| `asset_corp_bond` | 0 | 90 |
| `asset_mortgage_loan` | 40 | 100 |
| `funding_deposit` | 110 | 220 |
| `funding_wholesale` | 0 | 80 |
| `liquidity_shortfall` | 0 | 无上界 |

---

## 5. 约束条件（线性）

1. **总资产目标约束（等式）**  
   `asset_gov_bond + asset_corp_bond + asset_mortgage_loan = 200`

2. **资产负债平衡约束（等式）**  
   `asset_gov_bond + asset_corp_bond + asset_mortgage_loan - funding_deposit - funding_wholesale = 0`

3. **流动性覆盖约束（带软约束）**  
   `0.95*asset_gov_bond + 0.60*asset_corp_bond + 0.20*asset_mortgage_loan + liquidity_shortfall >= 120`

4. **久期暴露上限约束**  
   `2.0*asset_gov_bond + 4.0*asset_corp_bond + 6.0*asset_mortgage_loan <= 850`

5. **批发融资上限约束**  
   `funding_wholesale <= 60`

6. **企业债集中度上限约束**  
   `asset_corp_bond <= 70`

---

## 6. 优化目标

**目标方向：最大化**

最大化“净年化收益 - 流动性缺口惩罚”：

`0.038*asset_gov_bond + 0.062*asset_corp_bond + 0.075*asset_mortgage_loan`
`- 0.018*funding_deposit - 0.041*funding_wholesale - 0.5*liquidity_shortfall`

常数项：`0`

---

## 7. 备注

- 该文档为中文 Markdown 说明版测试输入，便于人工审阅。
- 若用于当前自动化 pipeline 执行，请使用 JSON 结构化输入文件。
