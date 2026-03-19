#!/usr/bin/env python3
"""Build and solve a linear programming model with OR-Tools."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from ortools.linear_solver import pywraplp
except ImportError:
    pywraplp = None  # type: ignore[assignment]


@dataclass
class Result:
    """Standard script result payload."""

    success: bool
    message: str
    exit_code: int
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Normalized LP input must be a JSON object.")
    return data


def _status_name(status_code: int) -> str:
    if pywraplp is None:
        return "NOT_AVAILABLE"
    candidates = [
        "OPTIMAL",
        "FEASIBLE",
        "INFEASIBLE",
        "UNBOUNDED",
        "ABNORMAL",
        "MODEL_INVALID",
        "NOT_SOLVED",
    ]
    for name in candidates:
        value = getattr(pywraplp.Solver, name, None)
        if value == status_code:
            return name
    return f"UNKNOWN_{status_code}"


def _constraint_activity(
    terms: list[dict[str, Any]], var_values: dict[str, float]
) -> float:
    return sum(float(t["coef"]) * var_values[str(t["var"])] for t in terms)


def solve_lp_model(
    model_spec: dict[str, Any], solver_name: str = "GLOP", time_limit_ms: int | None = None
) -> dict[str, Any]:
    if pywraplp is None:
        raise RuntimeError("ortools is not installed. Please install `ortools` first.")

    solver = pywraplp.Solver.CreateSolver(solver_name)
    if solver is None:
        raise RuntimeError(f"Could not create OR-Tools solver: {solver_name}")

    if time_limit_ms is not None:
        solver.SetTimeLimit(time_limit_ms)

    infinity = solver.infinity()
    variables: dict[str, pywraplp.Variable] = {}

    for var in model_spec["variables"]:
        name = str(var["name"])
        lb = -infinity if var["lb"] is None else float(var["lb"])
        ub = infinity if var["ub"] is None else float(var["ub"])
        variables[name] = solver.NumVar(lb, ub, name)

    constraints_map: dict[str, pywraplp.Constraint] = {}
    for c in model_spec["constraints"]:
        name = str(c["name"])
        lb = -infinity if c["lb"] is None else float(c["lb"])
        ub = infinity if c["ub"] is None else float(c["ub"])
        ct = solver.Constraint(lb, ub, name)
        for term in c["terms"]:
            ct.SetCoefficient(variables[str(term["var"])], float(term["coef"]))
        constraints_map[name] = ct

    objective = solver.Objective()
    for term in model_spec["objective"]["terms"]:
        objective.SetCoefficient(variables[str(term["var"])], float(term["coef"]))
    if model_spec["objective"]["sense"] == "max":
        objective.SetMaximization()
    else:
        objective.SetMinimization()

    status_code = solver.Solve()
    status = _status_name(status_code)
    has_primal_solution = status in {"OPTIMAL", "FEASIBLE"}

    variable_values = {
        name: float(var.solution_value()) for name, var in variables.items()
    } if has_primal_solution else {}

    objective_value = (
        float(objective.Value() + float(model_spec["objective"].get("constant", 0.0)))
        if has_primal_solution
        else None
    )

    constraints_output: list[dict[str, Any]] = []
    duals: dict[str, float] = {}
    for c in model_spec["constraints"]:
        name = str(c["name"])
        activity = _constraint_activity(c["terms"], variable_values) if has_primal_solution else None
        constraints_output.append(
            {
                "name": name,
                "lb": c["lb"],
                "ub": c["ub"],
                "activity": activity,
            }
        )
        if status == "OPTIMAL":
            try:
                duals[name] = float(constraints_map[name].dual_value())
            except Exception:
                # Backend may not expose duals in all solve states.
                pass

    reduced_costs: dict[str, float] = {}
    if status == "OPTIMAL":
        for name, var in variables.items():
            try:
                reduced_costs[name] = float(var.reduced_cost())
            except Exception:
                pass

    return {
        "solver": solver_name,
        "status": status,
        "objective_value": objective_value,
        "variable_values": variable_values,
        "constraints": constraints_output,
        "duals": duals,
        "reduced_costs": reduced_costs,
        "wall_time_ms": int(solver.wall_time()),
        "iterations": int(solver.iterations()),
    }


def run(input_path: Path, output_path: Path, solver_name: str, time_limit_ms: int | None) -> Result:
    """Run solve flow and return structured result."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model_spec = _load_json(input_path)
        solve_result = solve_lp_model(
            model_spec, solver_name=solver_name, time_limit_ms=time_limit_ms
        )
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(solve_result, f, ensure_ascii=True, indent=2)
        return Result(
            success=True,
            message=f"Solve result written to: {output_path}",
            exit_code=0,
            data={"output_path": str(output_path), "status": solve_result.get("status")},
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, RuntimeError) as exc:
        return Result(
            success=False,
            message="Invalid solver input or solver configuration.",
            exit_code=2,
            errors=[str(exc)],
        )
    except Exception as exc:
        return Result(
            success=False,
            message="Unexpected error during solve.",
            exit_code=1,
            errors=[str(exc)],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and solve LP with OR-Tools.")
    parser.add_argument("--input", required=True, help="Path to normalized LP JSON.")
    parser.add_argument("--output", required=True, help="Path to solution JSON.")
    parser.add_argument(
        "--solver",
        default="GLOP",
        help="OR-Tools linear solver backend (e.g., GLOP, PDLP).",
    )
    parser.add_argument(
        "--time-limit-ms",
        type=int,
        default=None,
        help="Optional solve time limit in milliseconds.",
    )
    args = parser.parse_args()

    try:
        result = run(
            input_path=Path(args.input),
            output_path=Path(args.output),
            solver_name=args.solver,
            time_limit_ms=args.time_limit_ms,
        )
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.success:
        print(result.message)
        if result.data.get("status"):
            print(f"Status: {result.data['status']}")
        sys.exit(0)

    print(f"Error: {result.message}", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
