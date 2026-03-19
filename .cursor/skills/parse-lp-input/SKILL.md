---
name: parse-lp-input
description: AI-first LP parsing skill. Use the model to extract variables/constraints/objective from any document, then use lightweight script helpers to normalize and validate LP JSON.
license: MIT
---

# parse-lp-input

## Purpose
Let the model perform document understanding and extraction, while script utilities only handle prompt/template generation and strict LP normalization.

## Triggers
- `extract LP model from any document with AI`
- `generate dynamic parser code for lp input`
- `normalize ai extracted variables constraints objective`
- `prepare model spec for ortools`

## I/O Contract

| Field | Type | Description |
|---|---|---|
| input_path | path | Source document path (any format) |
| extracted_json | path | AI-extracted LP JSON payload (recommended for non-JSON files) |
| emit_extraction_prompt | path | Optional output path for model extraction prompt |
| emit_parser_template | path | Optional output path for dynamic parser template code |
| output_path | path | Normalized JSON output path |
| output.variables | array | Variables with normalized bounds (`float` or `null`) |
| output.constraints | array | Constraint list referencing declared variables only |
| output.objective | object | Objective with validated sense and numeric coefficients |

## Process

### Phase 1 - Structural Validation
- If needed, emit an extraction prompt and parser template for model-driven parsing.
- Model extracts `variables`, `constraints`, `objective` from source documents.

### Phase 2 - Numeric Normalization
- Script validates only LP schema consistency and numeric bounds.
- Normalize numeric values to float.
- Preserve `null` for open bounds.

### Phase 3 - Emission
- Write canonical normalized JSON used by downstream skills.

## Scripts

### parse_lp_input.py
Path: `skills/parse-lp-input/scripts/parse_lp_input.py`

Usage:

```bash
python skills/parse-lp-input/scripts/parse_lp_input.py \
  --input examples/alm_lp_full_test_input.md \
  --extracted-json /tmp/ai_extracted_lp.json \
  --output examples/output/normalized_lp.json
```

Generate AI helper artifacts:

```bash
python skills/parse-lp-input/scripts/parse_lp_input.py \
  --input examples/alm_lp_full_test_input.md \
  --output examples/output/normalized_lp.json \
  --emit-extraction-prompt /tmp/extract_prompt.txt \
  --emit-parser-template /tmp/dynamic_parser.py
```

Exit Codes:
- `0`: Success.
- `1`: Unexpected runtime failure.
- `2`: Extraction/validation error (missing extracted JSON, schema/reference/bounds issues).

## Verification
- [ ] Prompt/template files are emitted when requested.
- [ ] AI-extracted JSON is normalized successfully with exit code `0`.
- [ ] Duplicate variable names fail with exit code `2`.
- [ ] Unknown variable references in objective/constraints fail with exit code `2`.

## Anti-Patterns
- Do not hardcode parser logic for every file format in this script.
- Do not skip model extraction for unstructured documents.
- Do not emit partial normalized output after validation errors.

## Extension Points
- Add automated evaluator prompts to score extraction quality before normalization.
- Add few-shot parser-template libraries for recurring vendor file layouts.
- Add domain-specific ALM business-rule prechecks after normalization.
