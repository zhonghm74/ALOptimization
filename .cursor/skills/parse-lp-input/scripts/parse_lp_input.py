#!/usr/bin/env python3
"""AI-first LP input normalizer with helper prompt/template emitters."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


NULL_TOKENS = {"", "null", "none", "na", "n/a", "nan", "无", "无上界", "inf", "+inf", "infinity", "∞"}


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


def _load_json_dict(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def _load_json_dict_from_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    for block in re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE):
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def _looks_like_lp_payload(raw: dict[str, Any]) -> bool:
    return all(k in raw for k in ("variables", "constraints", "objective"))


def _read_preview(input_path: Path, max_chars: int = 4000) -> str:
    text = input_path.read_text(encoding="utf-8", errors="ignore")
    text = text[:max_chars]
    if len(text) == max_chars:
        text += "\n...(truncated)"
    return text


def _build_extraction_prompt(input_path: Path) -> str:
    preview = _read_preview(input_path)
    return f"""You are extracting linear programming model data from an arbitrary document.

Document path: {input_path}

Task:
1) Read the document and infer LP components.
2) Build STRICT JSON with keys: metadata, variables, constraints, objective.
3) Ensure all constraint/objective variable references exist in variables.
4) Return ONLY JSON (no markdown fences, no explanation).

Required JSON schema:
{{
  "metadata": {{}},
  "variables": [
    {{"name": "x1", "lb": 0, "ub": null}}
  ],
  "constraints": [
    {{
      "name": "c1",
      "lb": null,
      "ub": 10,
      "terms": [{{"var": "x1", "coef": 1.0}}]
    }}
  ],
  "objective": {{
    "sense": "max",
    "terms": [{{"var": "x1", "coef": 1.0}}],
    "constant": 0
  }}
}}

Document preview:
\"\"\"
{preview}
\"\"\"
"""


def _build_dynamic_parser_template(input_path: Path) -> str:
    return f"""#!/usr/bin/env python3
\"\"\"Generated parser template for: {input_path}\"\"\"

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# TODO: customize extraction logic for your file format.
# Tip: use pandas/openpyxl/csv/re as needed.

INPUT_PATH = Path("{input_path}")
OUTPUT_PATH = Path("/tmp/ai_extracted_lp.json")


def extract_lp_payload(path: Path) -> dict[str, Any]:
    # Example placeholder:
    # text = path.read_text(encoding="utf-8")
    # parse text/table/... into variables/constraints/objective
    return {{
        "metadata": {{"source_file": str(path)}},
        "variables": [],
        "constraints": [],
        "objective": {{"sense": "max", "terms": [], "constant": 0}},
    }}


def main() -> None:
    payload = extract_lp_payload(INPUT_PATH)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"Wrote extracted payload to: {{OUTPUT_PATH}}")


if __name__ == "__main__":
    main()
"""


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
        name = name.strip()
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
        numeric_coef = _num_or_none(coef, f"objective.terms[{i}].coef")
        if numeric_coef is None:
            raise ValueError(f"objective.terms[{i}].coef must be numeric.")
        objective_terms.append({"var": var, "coef": float(numeric_coef)})

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
        name = name.strip()
        lb = _num_or_none(c.get("lb"), f"constraints[{i}].lb")
        ub = _num_or_none(c.get("ub"), f"constraints[{i}].ub")
        if lb is None and ub is None:
            raise ValueError(f"constraints[{i}] must specify at least one of lb or ub.")
        if lb is not None and ub is not None and lb > ub:
            raise ValueError(f"constraints[{i}] has lb > ub ({lb} > {ub}).")

        terms_raw = c.get("terms", [])
        if not isinstance(terms_raw, list) or not terms_raw:
            raise ValueError(f"constraints[{i}].terms must be a non-empty array.")

        terms: list[dict[str, Any]] = []
        for j, term in enumerate(terms_raw):
            if not isinstance(term, dict):
                raise ValueError(f"constraints[{i}].terms[{j}] must be an object.")
            var = term.get("var")
            coef = _num_or_none(term.get("coef"), f"constraints[{i}].terms[{j}].coef")
            if var not in variable_names:
                raise ValueError(f"constraints[{i}].terms[{j}].var references unknown variable: {var}")
            if coef is None:
                raise ValueError(f"constraints[{i}].terms[{j}].coef must be numeric.")
            terms.append({"var": var, "coef": float(coef)})

        constraints.append({"name": name, "lb": lb, "ub": ub, "terms": terms})

    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {"source_metadata": metadata}

    return {
        "metadata": metadata,
        "variables": variables,
        "constraints": constraints,
        "objective": objective,
    }


def _resolve_raw_payload(input_path: Path, extracted_json_path: Path | None) -> tuple[dict[str, Any], str]:
    if extracted_json_path is not None:
        return _load_json_dict(extracted_json_path), "ai_extracted_json"

    if input_path.suffix.lower() == ".json":
        raw = _load_json_dict(input_path)
        if _looks_like_lp_payload(raw):
            return raw, "direct_json"
        raise ValueError(
            "Input JSON does not contain variables/constraints/objective. "
            "Use --extracted-json with AI-extracted LP payload."
        )

    text = input_path.read_text(encoding="utf-8", errors="ignore")
    embedded = _load_json_dict_from_text(text)
    if embedded is not None and _looks_like_lp_payload(embedded):
        return embedded, "embedded_json_block"

    raise ValueError(
        "Non-JSON inputs require AI extraction first. "
        "Use --emit-extraction-prompt and/or --emit-parser-template, then pass --extracted-json."
    )


def run(
    input_path: Path,
    output_path: Path,
    extracted_json_path: Path | None = None,
    emit_extraction_prompt: Path | None = None,
    emit_parser_template: Path | None = None,
) -> Result:
    """Run AI-first extraction workflow and normalize payload."""
    try:
        warnings: list[str] = []
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if emit_extraction_prompt is not None:
            emit_extraction_prompt.parent.mkdir(parents=True, exist_ok=True)
            emit_extraction_prompt.write_text(_build_extraction_prompt(input_path), encoding="utf-8")
            warnings.append(f"Extraction prompt written to: {emit_extraction_prompt}")

        if emit_parser_template is not None:
            emit_parser_template.parent.mkdir(parents=True, exist_ok=True)
            emit_parser_template.write_text(
                _build_dynamic_parser_template(input_path), encoding="utf-8"
            )
            warnings.append(f"Dynamic parser template written to: {emit_parser_template}")

        raw, source_mode = _resolve_raw_payload(input_path, extracted_json_path)
        normalized = normalize_lp_input(raw)
        normalized.setdefault("metadata", {})
        normalized["metadata"]["parse_mode"] = source_mode
        normalized["metadata"]["source_file"] = str(input_path)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=True, indent=2)

        return Result(
            success=True,
            message=f"Normalized LP spec written to: {output_path}",
            exit_code=0,
            data={"output_path": str(output_path), "source_mode": source_mode},
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
        description="AI-first LP input parser (normalizer + prompt/template helpers)."
    )
    parser.add_argument("--input", required=True, help="Path to source document.")
    parser.add_argument("--output", required=True, help="Path to normalized output JSON.")
    parser.add_argument(
        "--extracted-json",
        type=Path,
        default=None,
        help="Path to AI-extracted LP JSON payload (recommended for non-JSON documents).",
    )
    parser.add_argument(
        "--emit-extraction-prompt",
        type=Path,
        default=None,
        help="Optional path to write an LLM extraction prompt template.",
    )
    parser.add_argument(
        "--emit-parser-template",
        type=Path,
        default=None,
        help="Optional path to write a dynamic parser Python template.",
    )
    args = parser.parse_args()

    try:
        result = run(
            input_path=Path(args.input),
            output_path=Path(args.output),
            extracted_json_path=args.extracted_json,
            emit_extraction_prompt=args.emit_extraction_prompt,
            emit_parser_template=args.emit_parser_template,
        )
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.success:
        print(result.message)
        print(f"Source mode: {result.data.get('source_mode')}")
        for warning in result.warnings:
            print(f"Note: {warning}")
        sys.exit(0)

    print(f"Error: {result.message}", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
