---
name: parse-lp-input
description: Use model reasoning to understand arbitrary documents and extract LP optimization elements (variables, constraints, objective) into a structured representation.
license: MIT
---

# parse-lp-input

## Purpose
read business documents and produce a complete, self-consistent LP problem definition.

## Triggers
- `extract LP model from any document with AI`
- `understand optimization constraints from document text`
- `identify variables constraints objective from report`
- `prepare model spec for ortools`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| Input | any document | Markdown/TXT/PDF/CSV/Excel/notes/specifications |
| Output.model_json | object | Structured LP JSON containing `variables`, `constraints`, `objective`, `metadata` |
| Output.problem_description_md | markdown | Human-readable problem statement (business background, objective, variables, constraints, assumptions) |
| Output.variable_name_map_cn | object | Full variable-name map `{english_name: chinese_name}` covering all variables in `model_json` |
| Output.model_json.variables | array | Variables with at least `name`, `lb`, `ub` (indexed or expanded per source granularity) |
| Output.model_json.constraints | array | Linear constraints with `name`, `lb/ub`, and `terms[{var,coef}]` |
| Output.model_json.objective | object | Objective with `sense`, `terms[{var,coef}]`, `constant` |
| Output.model_json.metadata | object | Case metadata, extraction notes, and assumption records |

## Indexing and Expansion Policy
- Preserve symbolic indexed forms by default (e.g., `x[t,Ai]`, `y[t,Lj]`, `s_liq[t]`, `r[t,Ai]`).
- Only apply time/index expansion when the source document explicitly requires concrete expanded names.
- Do not perform Cartesian expansion for static parameters or template constraints that are not explicitly expanded in the document.
- Keep constraints aligned with document granularity:
  - daily constraints remain in indexed form with quantifiers like `for each t=1..90`
  - cross-day constraints remain in indexed form with quantifiers like `for each t=2..90`
- Record expansion assumptions (if any) in `metadata.assumptions`.

## Process

### Phase 1 - Understand Business Context
- Identify planning horizon, units, and optimization intent.
- Separate descriptive text from enforceable constraints.

### Phase 2 - Extract LP Elements
- Enumerate decision variables and bounds.
- Convert business rules into linear constraints (`<=`, `>=`, `=`).
- Define objective direction (`max`/`min`) and coefficients.

### Phase 3 - Consistency Checks and Structured Output
- Ensure every variable in objective/constraints is declared.
- Ensure each constraint has at least one bound and one term.
- Resolve ambiguous wording by stating assumptions explicitly.
- Output machine-readable LP schema (`model_json`):
  - `variables: [{name, lb, ub}]`
  - `constraints: [{name, lb, ub, terms:[{var, coef}]}]`
  - `objective: {sense, terms:[{var, coef}], constant}`
- Build `variable_name_map_cn` for **all** variables in `model_json`.
- Generate `problem_description_md` to explain the problem in natural language.

## Verification
- [ ] All objective variables appear in `variables`.
- [ ] All constraint term variables appear in `variables`.
- [ ] All parameter variables are explicitly listed in `variables`.
- [ ] Every constraint has non-empty `terms` and at least one bound (`lb` or `ub`).
- [ ] Variable extraction follows source granularity: indexed variables stay indexed unless explicit expansion is requested.
- [ ] No unnecessary expansion of static parameters/constraints beyond the source document.
- [ ] `variable_name_map_cn` covers every variable name in `model_json.variables` (no missing Chinese names).
- [ ] `problem_description_md` explains objective, key variables, key constraints, and assumptions consistently with `model_json`.
- [ ] Output can be consumed by downstream solve/report skills without schema changes.

## Anti-Patterns
- Do not copy narrative text into coefficients without interpretation.
- Do not hide uncertain mappings; record assumptions explicitly.
- Do not invent constraints/objectives unsupported by source evidence.
- Do not materialize indexed templates into thousands of concrete variables unless the source explicitly asks for expansion.
- Do not output JSON variables without corresponding Chinese names in `variable_name_map_cn`.

## Extension Points
- Add domain-specific extraction checklists (ALM, supply chain, scheduling, etc.).
- Add confidence scores per extracted element for human review workflows.
- Add multi-pass extraction (coarse pass -> verification pass -> reconciliation pass).
