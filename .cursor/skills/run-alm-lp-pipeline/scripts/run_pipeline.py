#!/usr/bin/env python3
"""Run minimal end-to-end ALM LP pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from shutil import copyfile
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


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object.")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _validate_normalized_payload(path: Path) -> None:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("Normalized input must be a JSON object.")
    for required in ("variables", "constraints", "objective"):
        if required not in data:
            raise ValueError(f"Normalized input missing required field: {required}")


def _parse_range_1d(expr: str) -> list[int]:
    if ".." not in expr:
        raise ValueError(f"Unsupported index range: {expr}")
    left, right = expr.split("..", 1)
    start = int(left.strip())
    end = int(right.strip())
    if end < start:
        raise ValueError(f"Invalid index range: {expr}")
    return list(range(start, end + 1))


def _day_key(day_index: int) -> str:
    return f"D{day_index:02d}"


def _is_indexed_compact_payload(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict) and metadata.get("parse_mode") == "indexed_compact":
        return True
    names = {
        str(v.get("name"))
        for v in payload.get("variables", [])
        if isinstance(v, dict) and "name" in v
    }
    return "x[t,Ai]" in names and "y[t,Lj]" in names


def _index_templates(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    for item in payload.get("variables", []):
        if isinstance(item, dict) and "name" in item:
            templates[str(item["name"])] = item
    return templates


def _require_template(
    templates: dict[str, dict[str, Any]], name: str
) -> dict[str, Any]:
    if name not in templates:
        raise ValueError(f"Compact payload missing template variable: {name}")
    return templates[name]


def _extract_scalar_params(payload: dict[str, Any]) -> dict[str, float]:
    params: dict[str, float] = {}
    for item in payload.get("variables", []):
        if not isinstance(item, dict):
            continue
        if item.get("role") != "parameter":
            continue
        if "values" in item:
            continue
        if "lb" in item and "ub" in item and item["lb"] == item["ub"]:
            params[str(item["name"])] = float(item["lb"])
    return params


def _expand_indexed_compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Compact payload metadata must be an object.")

    index_sets = metadata.get("index_sets", {})
    if not isinstance(index_sets, dict):
        raise ValueError("Compact payload metadata.index_sets must be an object.")

    t_expr = index_sets.get("t")
    if not isinstance(t_expr, str):
        raise ValueError("Compact payload index_sets.t must be a range string like '1..90'.")
    t_values = _parse_range_1d(t_expr)

    asset_ids = index_sets.get("Ai")
    liab_ids = index_sets.get("Lj")
    if not isinstance(asset_ids, list) or not all(isinstance(x, str) for x in asset_ids):
        raise ValueError("Compact payload index_sets.Ai must be a string list.")
    if not isinstance(liab_ids, list) or not all(isinstance(x, str) for x in liab_ids):
        raise ValueError("Compact payload index_sets.Lj must be a string list.")

    templates = _index_templates(payload)
    x_tpl = _require_template(templates, "x[t,Ai]")
    y_tpl = _require_template(templates, "y[t,Lj]")
    s_liq_tpl = _require_template(templates, "s_liq[t]")
    s_dur_tpl = _require_template(templates, "s_dur[t]")
    r_tpl = _require_template(templates, "r[t,Ai]")
    c_tpl = _require_template(templates, "c[t,Lj]")
    w_tpl = _require_template(templates, "w[Ai]")
    d_tpl = _require_template(templates, "d[Ai]")
    delta_x_tpl = _require_template(templates, "delta_x[Ai]")
    delta_y_tpl = _require_template(templates, "delta_y[Lj]")

    x_bounds = x_tpl.get("bounds", {})
    y_bounds = y_tpl.get("bounds", {})
    if not isinstance(x_bounds, dict) or not isinstance(y_bounds, dict):
        raise ValueError("Decision variable templates must include bounds objects.")

    x_lb_by_asset = x_bounds.get("lower_by_Ai", {})
    x_ub_by_asset = x_bounds.get("upper_by_Ai", {})
    y_lb_by_liab = y_bounds.get("lower_by_Lj", {})
    y_ub_by_liab = y_bounds.get("upper_by_Lj", {})
    if not all(
        isinstance(obj, dict)
        for obj in (x_lb_by_asset, x_ub_by_asset, y_lb_by_liab, y_ub_by_liab)
    ):
        raise ValueError("Template bounds are missing per-instrument maps.")

    s_liq_bounds = s_liq_tpl.get("bounds", {})
    s_dur_bounds = s_dur_tpl.get("bounds", {})
    if not isinstance(s_liq_bounds, dict) or not isinstance(s_dur_bounds, dict):
        raise ValueError("Slack templates must include bounds objects.")

    r_values = r_tpl.get("values", {})
    c_values = c_tpl.get("values", {})
    w_values = w_tpl.get("values", {})
    d_values = d_tpl.get("values", {})
    delta_x_values = delta_x_tpl.get("values", {})
    delta_y_values = delta_y_tpl.get("values", {})
    if not all(
        isinstance(obj, dict)
        for obj in (
            r_values,
            c_values,
            w_values,
            d_values,
            delta_x_values,
            delta_y_values,
        )
    ):
        raise ValueError("Compact payload parameter templates must include values maps.")

    scalar_params = _extract_scalar_params(payload)
    total_assets_target = float(scalar_params.get("total_assets_target", 1200.0))
    liquidity_threshold = float(scalar_params.get("liquidity_threshold", 620.0))
    duration_cap = float(scalar_params.get("duration_exposure_cap", 4300.0))
    wholesale_cap = float(scalar_params.get("wholesale_funding_cap", 260.0))
    high_vol_cap = float(scalar_params.get("high_vol_assets_cap", 420.0))
    a15_cap = float(scalar_params.get("single_asset_a15_cap", 90.0))
    term_buffer = float(scalar_params.get("term_structure_buffer", 120.0))
    retail_ratio = float(scalar_params.get("retail_deposit_min_ratio", 0.45))
    penalty_s_liq = float(scalar_params.get("penalty_s_liq", 0.40))
    penalty_s_dur = float(scalar_params.get("penalty_s_dur", 0.25))
    day_divisor = float(scalar_params.get("daily_rate_denominator", 365.0))

    variables: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []
    objective_terms: list[dict[str, Any]] = []

    def x_name(day: int, aid: str) -> str:
        return f"x_{_day_key(day)}_{aid}"

    def y_name(day: int, lid: str) -> str:
        return f"y_{_day_key(day)}_{lid}"

    def s_liq_name(day: int) -> str:
        return f"s_liq_{_day_key(day)}"

    def s_dur_name(day: int) -> str:
        return f"s_dur_{_day_key(day)}"

    def _day_map(values: dict[str, Any], day: int, label: str) -> dict[str, Any]:
        key = _day_key(day)
        day_values = values.get(key)
        if not isinstance(day_values, dict):
            raise ValueError(f"Missing {label} values for day {key}")
        return day_values

    # Expanded variables and objective terms
    for t in t_values:
        day_key = _day_key(t)
        r_day = _day_map(r_values, t, "r[t,Ai]")
        c_day = _day_map(c_values, t, "c[t,Lj]")

        for aid in asset_ids:
            variables.append(
                {
                    "name": x_name(t, aid),
                    "lb": float(x_lb_by_asset[aid]),
                    "ub": float(x_ub_by_asset[aid]),
                }
            )
            objective_terms.append(
                {"var": x_name(t, aid), "coef": float(r_day[aid]) / day_divisor}
            )

        for lid in liab_ids:
            variables.append(
                {
                    "name": y_name(t, lid),
                    "lb": float(y_lb_by_liab[lid]),
                    "ub": float(y_ub_by_liab[lid]),
                }
            )
            objective_terms.append(
                {"var": y_name(t, lid), "coef": -float(c_day[lid]) / day_divisor}
            )

        variables.append(
            {
                "name": s_liq_name(t),
                "lb": float(s_liq_bounds.get("lower", 0.0)),
                "ub": s_liq_bounds.get("upper"),
            }
        )
        variables.append(
            {
                "name": s_dur_name(t),
                "lb": float(s_dur_bounds.get("lower", 0.0)),
                "ub": s_dur_bounds.get("upper"),
            }
        )
        objective_terms.append({"var": s_liq_name(t), "coef": -penalty_s_liq})
        objective_terms.append({"var": s_dur_name(t), "coef": -penalty_s_dur})

        # 1) total assets
        constraints.append(
            {
                "name": f"c_total_assets_{day_key}",
                "lb": total_assets_target,
                "ub": total_assets_target,
                "terms": [{"var": x_name(t, aid), "coef": 1.0} for aid in asset_ids],
            }
        )

        # 2) asset-liability balance
        constraints.append(
            {
                "name": f"c_balance_{day_key}",
                "lb": 0.0,
                "ub": 0.0,
                "terms": (
                    [{"var": x_name(t, aid), "coef": 1.0} for aid in asset_ids]
                    + [{"var": y_name(t, lid), "coef": -1.0} for lid in liab_ids]
                ),
            }
        )

        # 3) liquidity cover
        constraints.append(
            {
                "name": f"c_liquidity_cover_{day_key}",
                "lb": liquidity_threshold,
                "ub": None,
                "terms": (
                    [
                        {"var": x_name(t, aid), "coef": float(w_values[aid])}
                        for aid in asset_ids
                    ]
                    + [{"var": s_liq_name(t), "coef": 1.0}]
                ),
            }
        )

        # 4) duration cap
        constraints.append(
            {
                "name": f"c_duration_exposure_{day_key}",
                "lb": None,
                "ub": duration_cap,
                "terms": (
                    [
                        {"var": x_name(t, aid), "coef": float(d_values[aid])}
                        for aid in asset_ids
                    ]
                    + [{"var": s_dur_name(t), "coef": -1.0}]
                ),
            }
        )

        # 5) wholesale funding cap
        constraints.append(
            {
                "name": f"c_wholesale_funding_cap_{day_key}",
                "lb": None,
                "ub": wholesale_cap,
                "terms": [
                    {"var": y_name(t, "L06"), "coef": 1.0},
                    {"var": y_name(t, "L07"), "coef": 1.0},
                    {"var": y_name(t, "L08"), "coef": 1.0},
                ],
            }
        )

        # 6) high-vol assets cap
        constraints.append(
            {
                "name": f"c_high_vol_assets_cap_{day_key}",
                "lb": None,
                "ub": high_vol_cap,
                "terms": [
                    {"var": x_name(t, "A10"), "coef": 1.0},
                    {"var": x_name(t, "A11"), "coef": 1.0},
                    {"var": x_name(t, "A12"), "coef": 1.0},
                    {"var": x_name(t, "A14"), "coef": 1.0},
                    {"var": x_name(t, "A15"), "coef": 1.0},
                ],
            }
        )

        # 7) single asset A15 cap
        constraints.append(
            {
                "name": f"c_single_asset_a15_cap_{day_key}",
                "lb": None,
                "ub": a15_cap,
                "terms": [{"var": x_name(t, "A15"), "coef": 1.0}],
            }
        )

        # 8) term structure match
        constraints.append(
            {
                "name": f"c_term_structure_match_{day_key}",
                "lb": None,
                "ub": term_buffer,
                "terms": [
                    {"var": x_name(t, "A09"), "coef": 1.0},
                    {"var": x_name(t, "A10"), "coef": 1.0},
                    {"var": x_name(t, "A11"), "coef": 1.0},
                    {"var": x_name(t, "A12"), "coef": 1.0},
                    {"var": y_name(t, "L01"), "coef": -1.0},
                    {"var": y_name(t, "L02"), "coef": -1.0},
                    {"var": y_name(t, "L03"), "coef": -1.0},
                    {"var": y_name(t, "L04"), "coef": -1.0},
                ],
            }
        )

        # 9) retail deposit ratio
        constraints.append(
            {
                "name": f"c_retail_deposit_ratio_{day_key}",
                "lb": 0.0,
                "ub": None,
                "terms": [
                    {"var": y_name(t, "L01"), "coef": 1.0 - retail_ratio},
                    {"var": y_name(t, "L02"), "coef": 1.0 - retail_ratio},
                    {"var": y_name(t, "L03"), "coef": -retail_ratio},
                    {"var": y_name(t, "L04"), "coef": -retail_ratio},
                    {"var": y_name(t, "L05"), "coef": -retail_ratio},
                    {"var": y_name(t, "L06"), "coef": -retail_ratio},
                    {"var": y_name(t, "L07"), "coef": -retail_ratio},
                    {"var": y_name(t, "L08"), "coef": -retail_ratio},
                ],
            }
        )

    # 10) cross-day holding change constraints
    for t in t_values[1:]:
        day_key = _day_key(t)
        prev = t - 1
        for aid in asset_ids:
            lim = float(delta_x_values[aid])
            constraints.append(
                {
                    "name": f"c_turnover_x_{aid}_{day_key}",
                    "lb": -lim,
                    "ub": lim,
                    "terms": [
                        {"var": x_name(t, aid), "coef": 1.0},
                        {"var": x_name(prev, aid), "coef": -1.0},
                    ],
                }
            )
        for lid in liab_ids:
            lim = float(delta_y_values[lid])
            constraints.append(
                {
                    "name": f"c_turnover_y_{lid}_{day_key}",
                    "lb": -lim,
                    "ub": lim,
                    "terms": [
                        {"var": y_name(t, lid), "coef": 1.0},
                        {"var": y_name(prev, lid), "coef": -1.0},
                    ],
                }
            )

    expanded_metadata = dict(metadata)
    expanded_metadata["normalized_from"] = "indexed_compact"
    expanded_metadata["expanded_counts"] = {
        "variables": len(variables),
        "constraints": len(constraints),
        "objective_terms": len(objective_terms),
    }

    return {
        "variables": variables,
        "constraints": constraints,
        "objective": {
            "sense": "max",
            "terms": objective_terms,
            "constant": 0.0,
        },
        "metadata": expanded_metadata,
    }


def _prepare_normalized_input(input_path: Path, normalized_out: Path) -> list[str]:
    payload = _load_json(input_path)
    if _is_indexed_compact_payload(payload):
        expanded = _expand_indexed_compact_payload(payload)
        _write_json(normalized_out, expanded)
        return [
            "Input payload was indexed_compact; expanded to solver-ready normalized LP.",
        ]
    copyfile(input_path, normalized_out)
    return []


def run(
    input_path: Path,
    output_dir: Path,
    solver_name: str,
) -> Result:
    """Run solve/report stages from normalized LP input."""
    root = Path(__file__).resolve().parents[3]
    solve_script = root / "skills" / "build-and-solve-lp" / "scripts" / "build_and_solve_lp.py"
    report_script = (
        root / "skills" / "generate-lp-report" / "scripts" / "generate_lp_report.py"
    )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        normalized_out = output_dir / "normalized_lp.json"
        solution_out = output_dir / "solution.json"
        report_json_out = output_dir / "report.json"
        report_md_out = output_dir / "report.md"

        warnings = _prepare_normalized_input(input_path, normalized_out)
        _validate_normalized_payload(normalized_out)
        _run(
            [
                sys.executable,
                str(solve_script),
                "--input",
                str(normalized_out),
                "--output",
                str(solution_out),
                "--solver",
                solver_name,
            ]
        )
        _run(
            [
                sys.executable,
                str(report_script),
                "--normalized-input",
                str(normalized_out),
                "--solution",
                str(solution_out),
                "--report-json",
                str(report_json_out),
                "--report-md",
                str(report_md_out),
            ]
        )

        return Result(
            success=True,
            message="Pipeline finished successfully.",
            exit_code=0,
            data={
                "normalized_lp": str(normalized_out),
                "solution": str(solution_out),
                "report_json": str(report_json_out),
                "report_md": str(report_md_out),
            },
            warnings=warnings,
        )
    except (RuntimeError, ValueError) as exc:
        return Result(
            success=False,
            message="Pipeline stage failed.",
            exit_code=2,
            errors=[str(exc)],
        )
    except Exception as exc:
        return Result(
            success=False,
            message="Unexpected pipeline error.",
            exit_code=1,
            errors=[str(exc)],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run minimal ALM LP pipeline.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to normalized LP JSON (already extracted by parse-lp-input skill).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for pipeline outputs (copied normalized input, solution, report).",
    )
    parser.add_argument(
        "--solver",
        default="GLOP",
        help="OR-Tools linear solver backend (default: GLOP).",
    )
    args = parser.parse_args()

    try:
        result = run(
            input_path=Path(args.input),
            output_dir=Path(args.output_dir),
            solver_name=args.solver,
        )
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.success:
        print(result.message)
        print(f"- Normalized LP: {result.data['normalized_lp']}")
        print(f"- Solution: {result.data['solution']}")
        print(f"- Report JSON: {result.data['report_json']}")
        print(f"- Report MD: {result.data['report_md']}")
        sys.exit(0)

    print(f"Error: {result.message}", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
