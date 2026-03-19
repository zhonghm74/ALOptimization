#!/usr/bin/env python3
"""Generate chart report from tabular data."""

from __future__ import annotations

import argparse
import json
import re
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


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return cleaned[:120] if cleaned else "plot"


def _load_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise ValueError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix in {".xls", ".xlsx"}:
        df = pd.read_excel(path)
    elif suffix == ".json":
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            df = pd.DataFrame(obj)
        elif isinstance(obj, dict):
            if "data" in obj and isinstance(obj["data"], list):
                df = pd.DataFrame(obj["data"])
            elif "variables" in obj and isinstance(obj["variables"], list):
                df = pd.DataFrame(obj["variables"])
            else:
                df = pd.json_normalize(obj, max_level=1)
        else:
            raise ValueError("JSON root must be object or array.")
    else:
        raise ValueError(f"Unsupported input format: {suffix}")

    if df.empty or len(df.columns) == 0:
        raise ValueError("Input dataset is empty or has no columns.")
    return df


def _detect_datetime_cols(df: pd.DataFrame) -> list[str]:
    candidates: list[str] = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            candidates.append(str(col))
            continue
        if pd.api.types.is_object_dtype(df[col]):
            parsed = pd.to_datetime(df[col], errors="coerce")
            ratio = float(parsed.notna().mean())
            if ratio >= 0.8:
                candidates.append(str(col))
    return candidates


def _save_fig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def _line_chart(df: pd.DataFrame, x_col: str, y_col: str, out_path: Path) -> str:
    work = df[[x_col, y_col]].copy()
    work[x_col] = pd.to_datetime(work[x_col], errors="coerce")
    work = work.dropna()
    work = work.sort_values(by=x_col)
    if work.empty:
        raise ValueError(f"No valid values to plot line chart for {y_col}.")
    plt.figure(figsize=(10, 4.5))
    plt.plot(work[x_col], work[y_col], linewidth=1.5)
    plt.title(f"Line: {y_col} by {x_col}")
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    _save_fig(out_path)
    return f"line_{_safe_name(y_col)}_by_{_safe_name(x_col)}"


def _hist_chart(df: pd.DataFrame, col: str, out_path: Path) -> str:
    values = pd.to_numeric(df[col], errors="coerce").dropna()
    if values.empty:
        raise ValueError(f"No numeric values to plot histogram for {col}.")
    plt.figure(figsize=(7.5, 4.5))
    plt.hist(values, bins=30)
    plt.title(f"Histogram: {col}")
    plt.xlabel(col)
    plt.ylabel("Count")
    _save_fig(out_path)
    return f"hist_{_safe_name(col)}"


def _bar_chart(df: pd.DataFrame, col: str, out_path: Path) -> str:
    counts = df[col].astype("string").fillna("NULL").value_counts().head(20)
    if counts.empty:
        raise ValueError(f"No category values to plot bar chart for {col}.")
    plt.figure(figsize=(10, 4.8))
    plt.bar(counts.index.astype(str), counts.values)
    plt.xticks(rotation=45, ha="right")
    plt.title(f"Top Categories: {col}")
    plt.xlabel(col)
    plt.ylabel("Count")
    _save_fig(out_path)
    return f"bar_{_safe_name(col)}"


def _corr_heatmap(df: pd.DataFrame, numeric_cols: list[str], out_path: Path) -> str:
    corr = df[numeric_cols].corr(numeric_only=True)
    if corr.shape[0] < 2:
        raise ValueError("Need at least two numeric columns for heatmap.")
    plt.figure(figsize=(8, 6))
    im = plt.imshow(corr, cmap="coolwarm", vmin=-1.0, vmax=1.0, aspect="auto")
    plt.colorbar(im, fraction=0.046, pad=0.04)
    plt.xticks(range(len(corr.columns)), corr.columns, rotation=45, ha="right")
    plt.yticks(range(len(corr.index)), corr.index)
    plt.title("Correlation Heatmap")
    _save_fig(out_path)
    return "corr_heatmap"


def run(input_path: Path, output_dir: Path, max_numeric: int, max_categorical: int) -> Result:
    try:
        df = _load_df(input_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        numeric_cols = [
            str(c) for c in df.select_dtypes(include=["number"]).columns.tolist()
        ]
        datetime_cols = _detect_datetime_cols(df)
        categorical_cols = [
            str(c)
            for c in df.columns
            if str(c) not in numeric_cols and str(c) not in datetime_cols
        ]

        plots: list[dict[str, str]] = []
        warnings: list[str] = []

        # Line plots (datetime + numeric)
        if datetime_cols and numeric_cols:
            x_col = datetime_cols[0]
            for y_col in numeric_cols[: min(3, len(numeric_cols))]:
                filename = f"{len(plots)+1:02d}_line_{_safe_name(y_col)}.png"
                path = output_dir / filename
                try:
                    kind = _line_chart(df, x_col, y_col, path)
                    plots.append(
                        {
                            "kind": kind,
                            "title": f"Line: {y_col} by {x_col}",
                            "file": filename,
                        }
                    )
                except Exception as exc:
                    warnings.append(str(exc))

        # Histograms
        for col in numeric_cols[: max_numeric]:
            filename = f"{len(plots)+1:02d}_hist_{_safe_name(col)}.png"
            path = output_dir / filename
            try:
                kind = _hist_chart(df, col, path)
                plots.append(
                    {
                        "kind": kind,
                        "title": f"Histogram: {col}",
                        "file": filename,
                    }
                )
            except Exception as exc:
                warnings.append(str(exc))

        # Categorical bars
        for col in categorical_cols[: max_categorical]:
            filename = f"{len(plots)+1:02d}_bar_{_safe_name(col)}.png"
            path = output_dir / filename
            try:
                kind = _bar_chart(df, col, path)
                plots.append(
                    {
                        "kind": kind,
                        "title": f"Top Categories: {col}",
                        "file": filename,
                    }
                )
            except Exception as exc:
                warnings.append(str(exc))

        # Correlation heatmap
        if len(numeric_cols) >= 2:
            filename = f"{len(plots)+1:02d}_corr_heatmap.png"
            path = output_dir / filename
            try:
                kind = _corr_heatmap(df, numeric_cols[: min(20, len(numeric_cols))], path)
                plots.append(
                    {"kind": kind, "title": "Correlation Heatmap", "file": filename}
                )
            except Exception as exc:
                warnings.append(str(exc))

        if not plots:
            return Result(
                success=False,
                message="No plots were generated from input dataset.",
                exit_code=2,
                errors=["No numeric/categorical content could be visualized."],
                warnings=warnings,
            )

        summary = {
            "input_path": str(input_path),
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "numeric_columns": numeric_cols,
            "datetime_columns": datetime_cols,
            "categorical_columns": categorical_cols,
            "plots": plots,
            "warnings": warnings,
        }

        summary_path = output_dir / "summary.json"
        report_path = output_dir / "report.md"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        md_lines = [
            "# Data Visualization Report",
            "",
            f"- Input: `{input_path}`",
            f"- Rows: **{len(df)}**",
            f"- Columns: **{len(df.columns)}**",
            f"- Generated plots: **{len(plots)}**",
            "",
            "## Charts",
            "",
        ]
        for p in plots:
            md_lines.append(f"### {p['title']}")
            md_lines.append(f"![{p['title']}]({p['file']})")
            md_lines.append("")
        if warnings:
            md_lines.append("## Warnings")
            md_lines.append("")
            for w in warnings:
                md_lines.append(f"- {w}")
            md_lines.append("")

        report_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        return Result(
            success=True,
            message="Visualization report generated successfully.",
            exit_code=0,
            data={
                "summary_json": str(summary_path),
                "report_md": str(report_path),
                "plot_count": len(plots),
            },
            warnings=warnings,
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, pd.errors.ParserError) as exc:
        return Result(
            success=False,
            message="Invalid visualization input.",
            exit_code=2,
            errors=[str(exc)],
        )
    except Exception as exc:
        return Result(
            success=False,
            message="Unexpected visualization error.",
            exit_code=1,
            errors=[str(exc)],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate chart report from tabular data.")
    parser.add_argument("--input", required=True, help="Input dataset path (csv/json/xlsx).")
    parser.add_argument("--output-dir", required=True, help="Output directory for report assets.")
    parser.add_argument(
        "--max-numeric-plots",
        type=int,
        default=6,
        help="Maximum number of numeric-column plots.",
    )
    parser.add_argument(
        "--max-categorical-plots",
        type=int,
        default=3,
        help="Maximum number of categorical-column plots.",
    )
    args = parser.parse_args()

    result = run(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        max_numeric=max(1, args.max_numeric_plots),
        max_categorical=max(1, args.max_categorical_plots),
    )

    if result.success:
        print(result.message)
        print(f"- Summary JSON: {result.data['summary_json']}")
        print(f"- Report MD: {result.data['report_md']}")
        print(f"- Plot count: {result.data['plot_count']}")
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
