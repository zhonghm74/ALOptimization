#!/usr/bin/env python3
"""Parse and normalize ALM LP inputs from JSON/Markdown/TXT/CSV/Excel."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None


NULL_TOKENS = {"", "null", "none", "na", "n/a", "nan", "无", "无上界", "nonebound", "inf", "+inf", "infinity", "∞"}
VARIABLE_NAME_ALIASES = ["name", "variable", "var", "变量", "变量名"]
LOWER_BOUND_ALIASES = ["lb", "lower_bound", "lower", "min", "下界"]
UPPER_BOUND_ALIASES = ["ub", "upper_bound", "upper", "max", "上界"]
SECTION_ALIASES = ["section", "type", "record_type", "类别", "类型", "模块"]
CONSTRAINT_NAME_ALIASES = ["constraint_name", "constraint", "name", "约束名称", "约束"]
COEF_ALIASES = ["coef", "coefficient", "系数"]
SENSE_ALIASES = ["sense", "direction", "目标方向", "优化方向"]
CONSTANT_ALIASES = ["constant", "const", "常数项"]


@dataclass
class Result:
    """Standard script result payload."""

    success: bool
    message: str
    exit_code: int
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalize_key(value: str) -> str:
    return value.strip().lower()


def _clean_cell(value: Any) -> Any:
    if pd is not None:
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {_normalize_key(str(k)): _clean_cell(v) for k, v in row.items() if k is not None}


def _row_get(row: dict[str, Any], aliases: list[str], default: Any = None) -> Any:
    for alias in aliases:
        key = _normalize_key(alias)
        if key in row:
            return row[key]
    return default


def _num_or_none(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric or null, got boolean: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in NULL_TOKENS:
            return None
        try:
            return float(token)
        except ValueError as exc:
            raise ValueError(f"{field} must be numeric or null, got: {value!r}") from exc
    raise ValueError(f"{field} must be numeric or null, got: {value!r}")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Input JSON root must be an object.")
    return data


def _parse_linear_expression(expression: str) -> list[dict[str, Any]]:
    expr = expression.replace("−", "-").replace("—", "-").replace(" ", "").strip()
    if not expr:
        raise ValueError("Linear expression is empty.")
    if expr[0] not in "+-":
        expr = f"+{expr}"

    chunks = re.findall(r"([+-])([^+-]+)", expr)
    if not chunks:
        raise ValueError(f"Failed to parse expression: {expression}")

    aggregated: dict[str, float] = {}
    for sign, token in chunks:
        if not token:
            continue

        if "*" in token:
            coef_part, var_part = token.split("*", 1)
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var_part):
                raise ValueError(f"Invalid variable name in expression token: {token}")
            coef = float(coef_part) if coef_part else 1.0
            var = var_part
        else:
            match = re.fullmatch(r"([0-9]*\.?[0-9]+)?([A-Za-z_][A-Za-z0-9_]*)", token)
            if not match:
                raise ValueError(f"Invalid linear token: {token}")
            coef = float(match.group(1)) if match.group(1) else 1.0
            var = match.group(2)

        if sign == "-":
            coef *= -1.0
        aggregated[var] = aggregated.get(var, 0.0) + coef

    return [{"var": var, "coef": coef} for var, coef in aggregated.items() if abs(coef) > 1e-12]


def _parse_constraint_equation(equation: str, name: str) -> dict[str, Any]:
    match = re.search(r"(<=|>=|=)", equation)
    if not match:
        raise ValueError(f"Constraint equation missing comparator: {equation}")

    comparator = match.group(1)
    lhs = equation[: match.start()].strip()
    rhs_text = equation[match.end() :].strip()
    rhs = _num_or_none(rhs_text, f"constraint({name}).rhs")
    if rhs is None:
        raise ValueError(f"Constraint rhs must be numeric: {equation}")

    terms = _parse_linear_expression(lhs)
    if comparator == "=":
        lb = rhs
        ub = rhs
    elif comparator == "<=":
        lb = None
        ub = rhs
    else:
        lb = rhs
        ub = None

    return {"name": name, "lb": lb, "ub": ub, "terms": terms}


def _extract_markdown_section(text: str, heading_patterns: list[str]) -> str | None:
    for pattern in heading_patterns:
        found = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if found:
            remainder = text[found.end() :]
            next_heading = re.search(r"^\s*##\s+", remainder, re.MULTILINE)
            if next_heading:
                return remainder[: next_heading.start()]
            return remainder
    return None


def _parse_markdown_table(section_text: str) -> list[dict[str, str]]:
    lines = section_text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            current.append(stripped)
            continue
        if current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    for block in blocks:
        if len(block) < 3:
            continue
        if "---" not in block[1]:
            continue

        header = [cell.strip() for cell in block[0].strip("|").split("|")]
        rows: list[dict[str, str]] = []
        for raw_row in block[2:]:
            values = [cell.strip() for cell in raw_row.strip("|").split("|")]
            if len(values) < len(header):
                values.extend([""] * (len(header) - len(values)))
            rows.append(dict(zip(header, values[: len(header)])))
        return rows
    return []


def _extract_metadata_from_markdown(text: str) -> dict[str, Any]:
    section = _extract_markdown_section(text, [r"^\s*##\s*1\.\s*元数据", r"^\s*##\s*metadata"])
    if not section:
        return {}

    table_rows = _parse_markdown_table(section)
    metadata: dict[str, Any] = {}
    mapping = {
        "案例编号": "case_id",
        "案例名称": "case_name",
        "币种": "currency",
        "规划周期（月）": "time_horizon_months",
        "描述": "description",
        "case id": "case_id",
        "case name": "case_name",
        "currency": "currency",
        "horizon": "time_horizon_months",
        "description": "description",
    }
    for row in table_rows:
        normalized = _normalize_row(row)
        key_raw = _row_get(normalized, ["字段", "field"], "")
        value = _row_get(normalized, ["值", "value"], None)
        if not key_raw:
            continue
        mapped_key = mapping.get(str(key_raw).strip(), str(key_raw).strip())
        if mapped_key == "time_horizon_months":
            maybe_num = _num_or_none(value, "metadata.time_horizon_months")
            metadata[mapped_key] = int(maybe_num) if maybe_num is not None else None
        else:
            metadata[mapped_key] = value
    return metadata


def _extract_from_markdown_equations(text: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []

    variables_section = _extract_markdown_section(
        text,
        [
            r"^\s*##\s*4\.\s*决策变量范围",
            r"^\s*##\s*决策变量范围",
            r"^\s*##\s*variables?\b",
        ],
    )
    constraints_section = _extract_markdown_section(
        text,
        [
            r"^\s*##\s*5\.\s*约束条件",
            r"^\s*##\s*约束条件",
            r"^\s*##\s*constraints?\b",
        ],
    )
    objective_section = _extract_markdown_section(
        text,
        [
            r"^\s*##\s*6\.\s*优化目标",
            r"^\s*##\s*优化目标",
            r"^\s*##\s*objective\b",
        ],
    )

    if not variables_section or not constraints_section or not objective_section:
        raise ValueError("Markdown/TXT document is missing variable, constraint, or objective sections.")

    variable_rows = _parse_markdown_table(variables_section)
    if not variable_rows:
        raise ValueError("Failed to parse variables markdown table.")

    variables: list[dict[str, Any]] = []
    for row in variable_rows:
        normalized = _normalize_row(row)
        name = _row_get(normalized, VARIABLE_NAME_ALIASES)
        lb = _row_get(normalized, LOWER_BOUND_ALIASES)
        ub = _row_get(normalized, UPPER_BOUND_ALIASES)
        if not name:
            continue
        variables.append(
            {
                "name": str(name).strip("`").strip(),
                "lb": _num_or_none(lb, f"variable({name}).lb"),
                "ub": _num_or_none(ub, f"variable({name}).ub"),
            }
        )
    if not variables:
        raise ValueError("No variables extracted from markdown table.")

    constraints: list[dict[str, Any]] = []
    pending_name = ""
    auto_idx = 1
    for line in constraints_section.splitlines():
        stripped = line.strip()
        name_match = re.match(r"^\d+\.\s+\*\*(.+?)\*\*", stripped)
        if name_match:
            pending_name = name_match.group(1).strip()
            continue

        equation_matches = re.findall(r"`([^`]*(?:<=|>=|=)[^`]*)`", stripped)
        for eq in equation_matches:
            name = pending_name or f"c{auto_idx}"
            constraints.append(_parse_constraint_equation(eq, name))
            pending_name = ""
            auto_idx += 1

    if not constraints:
        raise ValueError("No constraints extracted from markdown equations.")

    objective_sense = "max"
    if re.search(r"(最小化|minimize|min)", objective_section, re.IGNORECASE):
        objective_sense = "min"
    elif re.search(r"(最大化|maximize|max)", objective_section, re.IGNORECASE):
        objective_sense = "max"
    else:
        warnings.append("Objective sense not found in text; defaulting to max.")

    objective_segments: list[str] = []
    for expression in re.findall(r"`([^`]*)`", objective_section):
        if re.search(r"(<=|>=|=)", expression):
            continue
        if re.search(r"[A-Za-z_][A-Za-z0-9_]*", expression):
            objective_segments.append(expression.strip())
    if not objective_segments:
        raise ValueError("No objective expression found in objective section.")

    objective_expression = "".join(objective_segments)
    objective_terms = _parse_linear_expression(objective_expression)

    constant_match = re.search(
        r"(?:常数项|constant)\s*[:：]\s*`?\s*([+-]?\d+(?:\.\d+)?)\s*`?",
        objective_section,
        re.IGNORECASE,
    )
    constant = float(constant_match.group(1)) if constant_match else 0.0
    if constant_match is None:
        warnings.append("Objective constant not found; defaulting to 0.")

    raw = {
        "metadata": _extract_metadata_from_markdown(text),
        "variables": variables,
        "constraints": constraints,
        "objective": {"sense": objective_sense, "terms": objective_terms, "constant": constant},
    }
    return raw, warnings


def _extract_fenced_json_by_section(text: str) -> dict[str, Any] | None:
    variables_match = re.search(
        r"(?:^|\n)(?:#+\s*)?(?:variables|变量)[^\n]*\n+```json\s*(\[[\s\S]*?\])\s*```",
        text,
        re.IGNORECASE,
    )
    constraints_match = re.search(
        r"(?:^|\n)(?:#+\s*)?(?:constraints|约束)[^\n]*\n+```json\s*(\[[\s\S]*?\])\s*```",
        text,
        re.IGNORECASE,
    )
    objective_match = re.search(
        r"(?:^|\n)(?:#+\s*)?(?:objective|目标)[^\n]*\n+```json\s*(\{[\s\S]*?\})\s*```",
        text,
        re.IGNORECASE,
    )
    if not (variables_match and constraints_match and objective_match):
        return None

    return {
        "variables": json.loads(variables_match.group(1)),
        "constraints": json.loads(constraints_match.group(1)),
        "objective": json.loads(objective_match.group(1)),
    }


def _extract_raw_json_object_from_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            candidate = json.loads(stripped)
            if isinstance(candidate, dict):
                return candidate
        except json.JSONDecodeError:
            pass

    for block in re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE):
        try:
            candidate = json.loads(block)
            if isinstance(candidate, dict):
                return candidate
        except json.JSONDecodeError:
            continue
    return None


def _extract_from_text_document(path: Path) -> tuple[dict[str, Any], str, list[str]]:
    text = path.read_text(encoding="utf-8")

    raw_json = _extract_raw_json_object_from_text(text)
    if raw_json is not None:
        return raw_json, "text-json", []

    fenced = _extract_fenced_json_by_section(text)
    if fenced is not None:
        return fenced, "text-fenced-json", []

    markdown_like, warnings = _extract_from_markdown_equations(text)
    return markdown_like, "text-markdown-equation", warnings


def _build_raw_from_section_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    variables: list[dict[str, Any]] = []
    constraints_map: dict[str, dict[str, Any]] = {}
    objective_terms: list[dict[str, Any]] = []
    objective_sense = "max"
    objective_constant = 0.0

    for row in rows:
        section = str(_row_get(row, SECTION_ALIASES, "") or "").strip().lower()
        if not section:
            continue

        if section in {"variable", "variables", "var", "vars", "变量"}:
            name = _row_get(row, VARIABLE_NAME_ALIASES)
            if not name:
                continue
            variables.append(
                {
                    "name": str(name).strip("`").strip(),
                    "lb": _num_or_none(_row_get(row, LOWER_BOUND_ALIASES), f"variable({name}).lb"),
                    "ub": _num_or_none(_row_get(row, UPPER_BOUND_ALIASES), f"variable({name}).ub"),
                }
            )
            continue

        if section in {"constraint", "constraints", "constraint_term", "约束"}:
            name_raw = _row_get(row, CONSTRAINT_NAME_ALIASES)
            var = _row_get(row, VARIABLE_NAME_ALIASES)
            coef = _row_get(row, COEF_ALIASES)
            if not (name_raw and var and coef is not None):
                continue
            name = str(name_raw).strip()
            if name not in constraints_map:
                constraints_map[name] = {"name": name, "lb": None, "ub": None, "terms": []}

            lb_value = _num_or_none(_row_get(row, LOWER_BOUND_ALIASES), f"constraint({name}).lb")
            ub_value = _num_or_none(_row_get(row, UPPER_BOUND_ALIASES), f"constraint({name}).ub")
            if lb_value is not None:
                constraints_map[name]["lb"] = lb_value
            if ub_value is not None:
                constraints_map[name]["ub"] = ub_value

            constraints_map[name]["terms"].append(
                {"var": str(var).strip("`").strip(), "coef": float(_num_or_none(coef, f"constraint({name}).coef") or 0.0)}
            )
            continue

        if section in {"objective", "objective_term", "objective_terms", "目标"}:
            var = _row_get(row, VARIABLE_NAME_ALIASES)
            coef = _row_get(row, COEF_ALIASES)
            if var and coef is not None:
                objective_terms.append(
                    {
                        "var": str(var).strip("`").strip(),
                        "coef": float(_num_or_none(coef, f"objective({var}).coef") or 0.0),
                    }
                )
            sense = _row_get(row, SENSE_ALIASES)
            if sense:
                token = str(sense).strip().lower()
                objective_sense = "min" if token in {"min", "minimize", "最小化"} else "max"
            constant = _row_get(row, CONSTANT_ALIASES)
            if constant is not None:
                objective_constant = float(_num_or_none(constant, "objective.constant") or 0.0)
            continue

        if section in {"objective_meta", "meta", "metadata", "目标元数据"}:
            sense = _row_get(row, SENSE_ALIASES)
            if sense:
                token = str(sense).strip().lower()
                objective_sense = "min" if token in {"min", "minimize", "最小化"} else "max"
            constant = _row_get(row, CONSTANT_ALIASES)
            if constant is not None:
                objective_constant = float(_num_or_none(constant, "objective.constant") or 0.0)

    constraints = list(constraints_map.values())
    if not variables or not constraints or not objective_terms:
        raise ValueError(
            "Failed to extract variables/constraints/objective from tabular rows. "
            "For CSV please include a section column: variables/constraints/objective."
        )

    return {
        "variables": variables,
        "constraints": constraints,
        "objective": {
            "sense": objective_sense,
            "terms": objective_terms,
            "constant": objective_constant,
        },
    }


def _extract_from_csv_document(path: Path) -> tuple[dict[str, Any], str, list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [_normalize_row(row) for row in reader]
    if not rows:
        raise ValueError("CSV file is empty.")
    raw = _build_raw_from_section_rows(rows)
    return raw, "csv-sectioned", []


def _extract_from_excel_document(path: Path) -> tuple[dict[str, Any], str, list[str]]:
    if pd is None:
        raise ValueError("Excel parsing requires pandas and openpyxl. Please install dependencies.")

    workbook = pd.ExcelFile(path)
    lower_to_original = {name.strip().lower(): name for name in workbook.sheet_names}

    def _find_sheet(candidates: list[str]) -> str | None:
        for candidate in candidates:
            key = candidate.strip().lower()
            if key in lower_to_original:
                return lower_to_original[key]
        return None

    variables_sheet = _find_sheet(["variables", "vars", "决策变量", "变量"])
    constraints_sheet = _find_sheet(["constraints", "constraint_terms", "约束"])
    objective_sheet = _find_sheet(["objective", "目标"])

    if variables_sheet and constraints_sheet and objective_sheet:
        var_rows = [_normalize_row(r) for r in pd.read_excel(path, sheet_name=variables_sheet).to_dict("records")]
        con_rows = [_normalize_row(r) for r in pd.read_excel(path, sheet_name=constraints_sheet).to_dict("records")]
        obj_rows = [_normalize_row(r) for r in pd.read_excel(path, sheet_name=objective_sheet).to_dict("records")]

        variables: list[dict[str, Any]] = []
        for row in var_rows:
            name = _row_get(row, VARIABLE_NAME_ALIASES)
            if not name:
                continue
            variables.append(
                {
                    "name": str(name).strip("`").strip(),
                    "lb": _num_or_none(_row_get(row, LOWER_BOUND_ALIASES), f"variable({name}).lb"),
                    "ub": _num_or_none(_row_get(row, UPPER_BOUND_ALIASES), f"variable({name}).ub"),
                }
            )

        constraints_map: dict[str, dict[str, Any]] = {}
        for row in con_rows:
            name_raw = _row_get(row, CONSTRAINT_NAME_ALIASES)
            var = _row_get(row, VARIABLE_NAME_ALIASES)
            coef = _row_get(row, COEF_ALIASES)
            if not (name_raw and var and coef is not None):
                continue
            name = str(name_raw).strip()
            if name not in constraints_map:
                constraints_map[name] = {"name": name, "lb": None, "ub": None, "terms": []}

            lb_value = _num_or_none(_row_get(row, LOWER_BOUND_ALIASES), f"constraint({name}).lb")
            ub_value = _num_or_none(_row_get(row, UPPER_BOUND_ALIASES), f"constraint({name}).ub")
            if lb_value is not None:
                constraints_map[name]["lb"] = lb_value
            if ub_value is not None:
                constraints_map[name]["ub"] = ub_value
            constraints_map[name]["terms"].append(
                {"var": str(var).strip("`").strip(), "coef": float(_num_or_none(coef, f"constraint({name}).coef") or 0.0)}
            )

        objective_terms: list[dict[str, Any]] = []
        objective_sense = "max"
        objective_constant = 0.0
        for row in obj_rows:
            var = _row_get(row, VARIABLE_NAME_ALIASES)
            coef = _row_get(row, COEF_ALIASES)
            if var and coef is not None:
                objective_terms.append(
                    {"var": str(var).strip("`").strip(), "coef": float(_num_or_none(coef, f"objective({var}).coef") or 0.0)}
                )
            sense = _row_get(row, SENSE_ALIASES)
            if sense:
                token = str(sense).strip().lower()
                objective_sense = "min" if token in {"min", "minimize", "最小化"} else "max"
            constant = _row_get(row, CONSTANT_ALIASES)
            if constant is not None:
                objective_constant = float(_num_or_none(constant, "objective.constant") or 0.0)

        raw = {
            "variables": variables,
            "constraints": list(constraints_map.values()),
            "objective": {"sense": objective_sense, "terms": objective_terms, "constant": objective_constant},
        }
        return raw, "excel-sheets", []

    default_sheet = workbook.sheet_names[0]
    rows = [_normalize_row(r) for r in pd.read_excel(path, sheet_name=default_sheet).to_dict("records")]
    if not rows:
        raise ValueError("Excel file is empty.")
    raw = _build_raw_from_section_rows(rows)
    return raw, "excel-sectioned", []


def _extract_raw_payload(input_path: Path) -> tuple[dict[str, Any], str, list[str]]:
    suffix = input_path.suffix.lower()
    if suffix == ".json":
        return _load_json(input_path), "json", []
    if suffix in {".md", ".markdown", ".txt"}:
        return _extract_from_text_document(input_path)
    if suffix == ".csv":
        return _extract_from_csv_document(input_path)
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return _extract_from_excel_document(input_path)
    raise ValueError(
        "Unsupported input format. Supported: .json, .md, .txt, .csv, .xlsx, .xlsm, .xls"
    )


def normalize_lp_input(raw: dict[str, Any]) -> dict[str, Any]:
    for required in ("variables", "constraints", "objective"):
        if required not in raw:
            raise ValueError(f"Missing required top-level field: {required}")

    variables_raw = raw["variables"]
    if not isinstance(variables_raw, list) or not variables_raw:
        raise ValueError("variables must be a non-empty array.")

    variables: list[dict[str, Any]] = []
    variable_names: set[str] = set()
    for i, var in enumerate(variables_raw):
        if not isinstance(var, dict):
            raise ValueError(f"variables[{i}] must be an object.")
        name = var.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"variables[{i}].name must be a non-empty string.")
        if name in variable_names:
            raise ValueError(f"Duplicate variable name: {name}")
        lb = _num_or_none(var.get("lb", 0.0), f"variables[{i}].lb")
        ub = _num_or_none(var.get("ub"), f"variables[{i}].ub")
        if lb is not None and ub is not None and lb > ub:
            raise ValueError(f"variables[{i}] has lb > ub ({lb} > {ub}).")
        variables.append({"name": name, "lb": lb, "ub": ub})
        variable_names.add(name)

    objective_raw = raw["objective"]
    if not isinstance(objective_raw, dict):
        raise ValueError("objective must be an object.")
    sense_raw = str(objective_raw.get("sense", "max")).strip().lower()
    sense = "min" if sense_raw in {"min", "minimize", "最小化"} else "max"
    if sense not in {"max", "min"}:
        raise ValueError("objective.sense must be 'max' or 'min'.")

    terms_raw = objective_raw.get("terms", [])
    if not isinstance(terms_raw, list) or not terms_raw:
        raise ValueError("objective.terms must be a non-empty array.")
    objective_terms: list[dict[str, Any]] = []
    for i, term in enumerate(terms_raw):
        if not isinstance(term, dict):
            raise ValueError(f"objective.terms[{i}] must be an object.")
        var = term.get("var")
        coef = term.get("coef")
        if var not in variable_names:
            raise ValueError(f"objective.terms[{i}].var references unknown variable: {var}")
        if not isinstance(coef, (int, float)):
            coef = _num_or_none(coef, f"objective.terms[{i}].coef")
        if coef is None:
            raise ValueError(f"objective.terms[{i}].coef must be numeric.")
        objective_terms.append({"var": var, "coef": float(coef)})

    objective = {
        "sense": sense,
        "terms": objective_terms,
        "constant": float(_num_or_none(objective_raw.get("constant", 0.0), "objective.constant") or 0.0),
    }

    constraints_raw = raw["constraints"]
    if not isinstance(constraints_raw, list):
        raise ValueError("constraints must be an array.")

    constraints: list[dict[str, Any]] = []
    for i, c in enumerate(constraints_raw):
        if not isinstance(c, dict):
            raise ValueError(f"constraints[{i}] must be an object.")
        name = c.get("name", f"c{i + 1}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"constraints[{i}].name must be a non-empty string when provided.")
        lb = _num_or_none(c.get("lb"), f"constraints[{i}].lb")
        ub = _num_or_none(c.get("ub"), f"constraints[{i}].ub")
        if lb is None and ub is None:
            raise ValueError(f"constraints[{i}] must specify at least one of lb or ub.")
        if lb is not None and ub is not None and lb > ub:
            raise ValueError(f"constraints[{i}] has lb > ub ({lb} > {ub}).")

        c_terms_raw = c.get("terms", [])
        if not isinstance(c_terms_raw, list) or not c_terms_raw:
            raise ValueError(f"constraints[{i}].terms must be a non-empty array.")

        c_terms: list[dict[str, Any]] = []
        for j, term in enumerate(c_terms_raw):
            if not isinstance(term, dict):
                raise ValueError(f"constraints[{i}].terms[{j}] must be an object.")
            var = term.get("var")
            coef = term.get("coef")
            if var not in variable_names:
                raise ValueError(
                    f"constraints[{i}].terms[{j}].var references unknown variable: {var}"
                )
            if not isinstance(coef, (int, float)):
                coef = _num_or_none(coef, f"constraints[{i}].terms[{j}].coef")
            if coef is None:
                raise ValueError(f"constraints[{i}].terms[{j}].coef must be numeric.")
            c_terms.append({"var": var, "coef": float(coef)})

        constraints.append({"name": name, "lb": lb, "ub": ub, "terms": c_terms})

    return {
        "metadata": raw.get("metadata", {}),
        "variables": variables,
        "constraints": constraints,
        "objective": objective,
    }


def run(input_path: Path, output_path: Path) -> Result:
    """Run extraction + normalization flow and return structured result."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        raw, source_format, warnings = _extract_raw_payload(input_path)
        normalized = normalize_lp_input(raw)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=True, indent=2)
        return Result(
            success=True,
            message=f"Normalized LP spec written to: {output_path}",
            exit_code=0,
            data={"output_path": str(output_path), "source_format": source_format},
            warnings=warnings,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        return Result(
            success=False,
            message="Input extraction/validation failed.",
            exit_code=2,
            errors=[str(exc)],
        )
    except Exception as exc:
        return Result(
            success=False,
            message="Unexpected error while parsing LP input.",
            exit_code=1,
            errors=[str(exc)],
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse and normalize LP input from JSON/Markdown/TXT/CSV/Excel."
    )
    parser.add_argument("--input", required=True, help="Path to input file.")
    parser.add_argument("--output", required=True, help="Path to normalized output JSON.")
    args = parser.parse_args()

    try:
        result = run(Path(args.input), Path(args.output))
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.success:
        print(result.message)
        if result.data.get("source_format"):
            print(f"Detected source format: {result.data['source_format']}")
        for warning in result.warnings:
            print(f"Warning: {warning}")
        sys.exit(0)

    print(f"Error: {result.message}", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
