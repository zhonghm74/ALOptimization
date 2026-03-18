#!/usr/bin/env python3
"""Run minimal end-to-end ALM LP pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run minimal ALM LP pipeline.")
    parser.add_argument("--input", required=True, help="Path to raw LP input JSON.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for pipeline outputs (normalized, solution, report).",
    )
    parser.add_argument(
        "--solver",
        default="GLOP",
        help="OR-Tools linear solver backend (default: GLOP).",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    parse_script = root / "skills" / "parse-lp-input" / "scripts" / "parse_lp_input.py"
    solve_script = root / "skills" / "build-and-solve-lp" / "scripts" / "build_and_solve_lp.py"
    report_script = (
        root / "skills" / "generate-alm-report" / "scripts" / "generate_alm_report.py"
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    normalized_out = output_dir / "normalized_lp.json"
    solution_out = output_dir / "solution.json"
    report_json_out = output_dir / "report.json"
    report_md_out = output_dir / "report.md"

    _run(
        [
            sys.executable,
            str(parse_script),
            "--input",
            str(Path(args.input)),
            "--output",
            str(normalized_out),
        ]
    )
    _run(
        [
            sys.executable,
            str(solve_script),
            "--input",
            str(normalized_out),
            "--output",
            str(solution_out),
            "--solver",
            args.solver,
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

    print("Pipeline finished successfully.")
    print(f"- Normalized LP: {normalized_out}")
    print(f"- Solution: {solution_out}")
    print(f"- Report JSON: {report_json_out}")
    print(f"- Report MD: {report_md_out}")


if __name__ == "__main__":
    main()
