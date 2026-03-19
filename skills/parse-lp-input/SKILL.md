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
| Output.variables | array | Decision variables with `name`, `lb`, `ub` |
| Output.constraints | array | Linear constraints with `name`, `lb/ub`, and `terms[{var,coef}]` |
| Output.objective | object | Objective with `sense`, `terms[{var,coef}]`, `constant` |
| Output.metadata | object | Optional case metadata and extraction notes |

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
- Output machine-readable LP schema:
  - `variables: [{name, lb, ub}]`
  - `constraints: [{name, lb, ub, terms:[{var, coef}]}]`
  - `objective: {sense, terms:[{var, coef}], constant}`

## Verification
- [ ] All objective variables appear in `variables`.
- [ ] All constraint term variables appear in `variables`.
- [ ] All parameter variables are explicitly listed in `variables`.
- [ ] Every constraint has non-empty `terms` and at least one bound (`lb` or `ub`).
- [ ] Output can be consumed by downstream solve/report skills without schema changes.

## Anti-Patterns
- Do not copy narrative text into coefficients without interpretation.
- Do not hide uncertain mappings; record assumptions explicitly.
- Do not invent constraints/objectives unsupported by source evidence.

## Extension Points
- Add domain-specific extraction checklists (ALM, supply chain, scheduling, etc.).
- Add confidence scores per extracted element for human review workflows.
- Add multi-pass extraction (coarse pass -> verification pass -> reconciliation pass).
