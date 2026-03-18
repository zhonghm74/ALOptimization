---
name: parse-lp-input
description: Validate and normalize an ALM linear programming input file when constraints and objective are provided by the user as data.
---

# parse-lp-input

## Purpose
Convert a raw JSON input file into a validated, normalized LP specification that can be consumed by OR-Tools.

## Input
- `input_path`: JSON file with `variables`, `constraints`, and `objective`.
- `output_path`: target path for normalized JSON.

## Output
- A normalized JSON file with:
  - deduplicated variable names
  - numeric bounds normalized to float or null
  - coefficient terms validated against declared variables

## Script
Use:

```bash
python skills/parse-lp-input/scripts/parse_lp_input.py \
  --input examples/input/alm_lp_input.json \
  --output examples/output/normalized_lp.json
```
