#!/usr/bin/env python3
"""Generate a concise ALM optimization report."""

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


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _build_report(normalized: dict[str, Any], solution: dict[str, Any]) -> dict[str, Any]:
    status = str(solution.get("status", "UNKNOWN"))
    objective_value = solution.get("objective_value")
    variable_values = solution.get("variable_values", {})

    non_zero_vars = [
        {"name": name, "value": float(value)}
        for name, value in variable_values.items()
        if abs(float(value)) > 1e-9
    ]
    non_zero_vars.sort(key=lambda x: abs(x["value"]), reverse=True)

    constraint_checks: list[dict[str, Any]] = []
    for c in solution.get("constraints", []):
        lb = c.get("lb")
        ub = c.get("ub")
        activity = c.get("activity")
        satisfied = None
        if activity is not None:
            lower_ok = True if lb is None else (activity >= lb - 1e-7)
            upper_ok = True if ub is None else (activity <= ub + 1e-7)
            satisfied = bool(lower_ok and upper_ok)
        constraint_checks.append(
            {
                "name": c.get("name"),
                "activity": activity,
                "lb": lb,
                "ub": ub,
                "satisfied": satisfied,
            }
        )

    return {
        "metadata": normalized.get("metadata", {}),
        "solver": solution.get("solver"),
        "status": status,
        "objective_value": objective_value,
        "non_zero_variables": non_zero_vars,
        "constraint_checks": constraint_checks,
        "duals": solution.get("duals", {}),
        "reduced_costs": solution.get("reduced_costs", {}),
        "summary": {
            "variable_count": len(normalized.get("variables", [])),
            "constraint_count": len(normalized.get("constraints", [])),
            "non_zero_variable_count": len(non_zero_vars),
        },
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# ALM Optimization Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Status: **{report['status']}**")
    lines.append(f"- Solver: `{report.get('solver', 'unknown')}`")
    lines.append(f"- Objective Value: `{report.get('objective_value')}`")
    lines.append(
        f"- Variables / Constraints: "
        f"{report['summary']['variable_count']} / {report['summary']['constraint_count']}"
    )
    lines.append("")

    lines.append("## Top Non-zero Decision Variables")
    lines.append("")
    if report["non_zero_variables"]:
        lines.append("| Variable | Value |")
        lines.append("|---|---:|")
        for row in report["non_zero_variables"][:20]:
            lines.append(f"| {row['name']} | {row['value']:.6f} |")
    else:
        lines.append("- No non-zero variable assignments were produced.")
    lines.append("")

    lines.append("## Constraint Satisfaction")
    lines.append("")
    lines.append("| Constraint | Activity | Lower | Upper | Satisfied |")
    lines.append("|---|---:|---:|---:|:---:|")
    for c in report["constraint_checks"]:
        activity = "null" if c["activity"] is None else f"{c['activity']:.6f}"
        lower = "null" if c["lb"] is None else f"{c['lb']:.6f}"
        upper = "null" if c["ub"] is None else f"{c['ub']:.6f}"
        satisfied = "n/a" if c["satisfied"] is None else ("yes" if c["satisfied"] else "no")
        lines.append(f"| {c['name']} | {activity} | {lower} | {upper} | {satisfied} |")

    return "\n".join(lines) + "\n"


def run(
    normalized_input_path: Path,
    solution_path: Path,
    report_json_path: Path,
    report_md_path: Path,
) -> Result:
    """Run report generation and return structured result."""
    try:
        normalized = _load_json(normalized_input_path)
        solution = _load_json(solution_path)
        report = _build_report(normalized, solution)

        report_json_path.parent.mkdir(parents=True, exist_ok=True)
        report_md_path.parent.mkdir(parents=True, exist_ok=True)

        with report_json_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=True, indent=2)
        with report_md_path.open("w", encoding="utf-8") as f:
            f.write(_to_markdown(report))

        return Result(
            success=True,
            message="ALM report generated successfully.",
            exit_code=0,
            data={
                "report_json_path": str(report_json_path),
                "report_md_path": str(report_md_path),
            },
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return Result(
            success=False,
            message="Invalid reporting input artifacts.",
            exit_code=2,
            errors=[str(exc)],
        )
    except Exception as exc:
        return Result(
            success=False,
            message="Unexpected error while generating report.",
            exit_code=1,
            errors=[str(exc)],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ALM report from LP solution.")
    parser.add_argument("--normalized-input", required=True, help="Path to normalized LP JSON.")
    parser.add_argument("--solution", required=True, help="Path to solver output JSON.")
    parser.add_argument("--report-json", required=True, help="Path to output report JSON.")
    parser.add_argument("--report-md", required=True, help="Path to output markdown report.")
    args = parser.parse_args()

    try:
        result = run(
            normalized_input_path=Path(args.normalized_input),
            solution_path=Path(args.solution),
            report_json_path=Path(args.report_json),
            report_md_path=Path(args.report_md),
        )
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.success:
        print(result.message)
        print(f"Report JSON written to: {result.data['report_json_path']}")
        print(f"Report Markdown written to: {result.data['report_md_path']}")
        sys.exit(0)

    print(f"Error: {result.message}", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
