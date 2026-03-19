#!/usr/bin/env python3
"""Visualize LP solver diagnostics from solution JSON."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


@dataclass
class Result:
    success: bool
    message: str
    exit_code: int
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _load_solution(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Solution file not found: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Solution JSON must be an object.")
    if "variable_values" not in obj or "constraints" not in obj:
        raise ValueError("Solution JSON missing required fields: variable_values / constraints")
    if not isinstance(obj["variable_values"], dict):
        raise ValueError("solution.variable_values must be an object map.")
    if not isinstance(obj["constraints"], list):
        raise ValueError("solution.constraints must be an array.")
    return obj


def _save_fig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def _plot_top_variables(df: pd.DataFrame, out_path: Path, top_n: int) -> int:
    if df.empty:
        return 0
    top = df.sort_values("abs_value", ascending=False).head(top_n).iloc[::-1]
    plt.figure(figsize=(10, max(4.5, 0.25 * len(top))))
    colors = ["#4472C4" if v >= 0 else "#C0504D" for v in top["value"]]
    plt.barh(top["name"], top["value"], color=colors)
    plt.title(f"Top {len(top)} Non-zero Variables")
    plt.xlabel("Value")
    plt.ylabel("Variable")
    _save_fig(out_path)
    return int(len(top))


def _constraint_margin(row: dict[str, Any]) -> float | None:
    activity = row.get("activity")
    lb = row.get("lb")
    ub = row.get("ub")
    if activity is None:
        return None
    margins: list[float] = []
    if lb is not None:
        margins.append(float(activity) - float(lb))
    if ub is not None:
        margins.append(float(ub) - float(activity))
    if not margins:
        return None
    return min(margins)


def _plot_margin_hist(margins: list[float], out_path: Path) -> bool:
    if not margins:
        return False
    plt.figure(figsize=(8, 4.8))
    plt.hist(margins, bins=30)
    plt.title("Constraint Margin Distribution")
    plt.xlabel("Margin to nearest bound")
    plt.ylabel("Count")
    _save_fig(out_path)
    return True


def _plot_tightest(df: pd.DataFrame, out_path: Path, top_n: int = 25) -> int:
    if df.empty:
        return 0
    tight = df.nsmallest(top_n, "margin").iloc[::-1]
    plt.figure(figsize=(10, max(4.5, 0.25 * len(tight))))
    plt.barh(tight["name"], tight["margin"], color="#8064A2")
    plt.title(f"Tightest {len(tight)} Constraints (Lower margin = tighter)")
    plt.xlabel("Margin")
    plt.ylabel("Constraint")
    _save_fig(out_path)
    return int(len(tight))


def run(solution_path: Path, output_dir: Path, top_n: int) -> Result:
    try:
        solution = _load_solution(solution_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Variables
        var_items = [
            {"name": k, "value": float(v), "abs_value": abs(float(v))}
            for k, v in solution["variable_values"].items()
            if abs(float(v)) > 1e-9
        ]
        var_df = pd.DataFrame(var_items)

        # Constraint margins
        c_rows: list[dict[str, Any]] = []
        for c in solution["constraints"]:
            if not isinstance(c, dict):
                continue
            margin = _constraint_margin(c)
            if margin is None:
                continue
            c_rows.append({"name": str(c.get("name", "unknown")), "margin": float(margin)})
        c_df = pd.DataFrame(c_rows)

        charts: list[dict[str, str]] = []
        warnings: list[str] = []

        top_vars_file = "top_variables.png"
        top_vars_count = _plot_top_variables(var_df, output_dir / top_vars_file, top_n=top_n)
        if top_vars_count > 0:
            charts.append(
                {
                    "kind": "top_variables",
                    "title": f"Top {top_vars_count} Non-zero Variables",
                    "file": top_vars_file,
                }
            )
        else:
            warnings.append("No non-zero variables found for top-variable chart.")

        margin_hist_file = "constraint_margin_hist.png"
        if _plot_margin_hist(c_df["margin"].tolist() if not c_df.empty else [], output_dir / margin_hist_file):
            charts.append(
                {
                    "kind": "constraint_margin_hist",
                    "title": "Constraint Margin Distribution",
                    "file": margin_hist_file,
                }
            )
        else:
            warnings.append("No constraint margins available for histogram.")

        tight_file = "tightest_constraints.png"
        tight_count = _plot_tightest(c_df, output_dir / tight_file, top_n=25)
        if tight_count > 0:
            charts.append(
                {
                    "kind": "tightest_constraints",
                    "title": f"Tightest {tight_count} Constraints",
                    "file": tight_file,
                }
            )
        else:
            warnings.append("No tight-constraint chart generated.")

        if not charts:
            return Result(
                success=False,
                message="No diagnostic charts generated.",
                exit_code=2,
                errors=["Solver result did not contain plottable variable or constraint data."],
                warnings=warnings,
            )

        summary = {
            "solution_path": str(solution_path),
            "status": str(solution.get("status", "UNKNOWN")),
            "objective_value": solution.get("objective_value"),
            "non_zero_variable_count": int(len(var_df)),
            "margin_constraint_count": int(len(c_df)),
            "charts": charts,
            "warnings": warnings,
        }

        summary_path = output_dir / "summary.json"
        report_path = output_dir / "report.md"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        lines = [
            "# Optimization Diagnostics Visualization",
            "",
            f"- Solution: `{solution_path}`",
            f"- Status: **{summary['status']}**",
            f"- Objective Value: `{summary['objective_value']}`",
            f"- Non-zero variables: **{summary['non_zero_variable_count']}**",
            f"- Constraints with computable margin: **{summary['margin_constraint_count']}**",
            "",
            "## Charts",
            "",
        ]
        for c in charts:
            lines.append(f"### {c['title']}")
            lines.append(f"![{c['title']}]({c['file']})")
            lines.append("")
        if warnings:
            lines.append("## Warnings")
            lines.append("")
            for w in warnings:
                lines.append(f"- {w}")
            lines.append("")

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return Result(
            success=True,
            message="Optimization diagnostics charts generated successfully.",
            exit_code=0,
            data={
                "summary_json": str(summary_path),
                "report_md": str(report_path),
                "chart_count": len(charts),
            },
            warnings=warnings,
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return Result(
            success=False,
            message="Invalid optimization result input.",
            exit_code=2,
            errors=[str(exc)],
        )
    except Exception as exc:
        return Result(
            success=False,
            message="Unexpected diagnostics visualization error.",
            exit_code=1,
            errors=[str(exc)],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize LP solution diagnostics.")
    parser.add_argument("--solution", required=True, help="Path to solver solution JSON.")
    parser.add_argument("--output-dir", required=True, help="Output directory for visualization report.")
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Top N non-zero variables to plot.",
    )
    args = parser.parse_args()

    result = run(
        solution_path=Path(args.solution),
        output_dir=Path(args.output_dir),
        top_n=max(5, args.top_n),
    )

    if result.success:
        print(result.message)
        print(f"- Summary JSON: {result.data['summary_json']}")
        print(f"- Report MD: {result.data['report_md']}")
        print(f"- Chart count: {result.data['chart_count']}")
        if result.warnings:
            print("- Warnings:")
            for w in result.warnings:
                print(f"  - {w}")
        sys.exit(0)

    print(f"Error: {result.message}", file=sys.stderr)
    for err in result.errors:
        print(f"  - {err}", file=sys.stderr)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
