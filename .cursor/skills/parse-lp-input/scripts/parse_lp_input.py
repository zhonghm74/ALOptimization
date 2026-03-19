#!/usr/bin/env python3
"""Workspace wrapper for parse-lp-input parser script."""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    source = Path(__file__).resolve().parents[4] / "skills" / "parse-lp-input" / "scripts" / "parse_lp_input.py"
    runpy.run_path(str(source), run_name="__main__")


if __name__ == "__main__":
    main()

