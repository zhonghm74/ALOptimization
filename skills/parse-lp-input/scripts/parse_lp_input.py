#!/usr/bin/env python3
"""Validate and normalize LP input JSON for ALM optimization."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Result:
    """Standard script result payload."""

    success: bool
    message: str
    exit_code: int
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _num_or_none(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"{field} must be a number or null, got: {value!r}")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Input JSON root must be an object.")
    return data


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
    sense = objective_raw.get("sense", "max")
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
            raise ValueError(f"objective.terms[{i}].coef must be numeric.")
        objective_terms.append({"var": var, "coef": float(coef)})

    objective = {
        "sense": sense,
        "terms": objective_terms,
        "constant": float(objective_raw.get("constant", 0.0)),
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
    """Run normalization flow and return structured result."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        raw = _load_json(input_path)
        normalized = normalize_lp_input(raw)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=True, indent=2)
        return Result(
            success=True,
            message=f"Normalized LP spec written to: {output_path}",
            exit_code=0,
            data={"output_path": str(output_path)},
        )
    except (ValueError, json.JSONDecodeError) as exc:
        return Result(
            success=False,
            message="Input validation failed.",
            exit_code=2,
            errors=[str(exc)],
        )
    except Exception as exc:
        return Result(
            success=False,
            message="Unexpected error while normalizing LP input.",
            exit_code=1,
            errors=[str(exc)],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse and normalize LP input JSON.")
    parser.add_argument("--input", required=True, help="Path to raw input JSON.")
    parser.add_argument("--output", required=True, help="Path to normalized output JSON.")
    args = parser.parse_args()

    try:
        result = run(Path(args.input), Path(args.output))
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.success:
        print(result.message)
        sys.exit(0)

    print(f"Error: {result.message}", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
