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


def _validate_normalized_payload(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Normalized input must be a JSON object.")
    for required in ("variables", "constraints", "objective"):
        if required not in data:
            raise ValueError(f"Normalized input missing required field: {required}")


def run(
    input_path: Path,
    output_dir: Path,
    solver_name: str,
) -> Result:
    """Run solve/report stages from normalized LP input."""
    root = Path(__file__).resolve().parents[3]
    solve_script = root / "skills" / "build-and-solve-lp" / "scripts" / "build_and_solve_lp.py"
    report_script = (
        root / "skills" / "generate-alm-report" / "scripts" / "generate_alm_report.py"
    )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        normalized_out = output_dir / "normalized_lp.json"
        solution_out = output_dir / "solution.json"
        report_json_out = output_dir / "report.json"
        report_md_out = output_dir / "report.md"

        _validate_normalized_payload(input_path)
        copyfile(input_path, normalized_out)
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
