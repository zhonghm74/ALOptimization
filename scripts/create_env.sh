#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found in PATH." >&2
  exit 1
fi

echo "Creating virtual environment in ${VENV_DIR}..."
python3 -m venv "${VENV_DIR}"

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "Upgrading pip tooling..."
python -m pip install --upgrade pip setuptools wheel

echo "Installing dependencies from requirements.txt..."
python -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
else
  echo ".env already exists; leaving it unchanged."
fi

echo "Environment setup complete."
echo "Activate it with: source ${VENV_DIR}/bin/activate"
