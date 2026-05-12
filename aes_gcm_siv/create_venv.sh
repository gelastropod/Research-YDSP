#!/usr/bin/env bash
# Create a local virtual environment and install requirements
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
fi
# Freeze installed packages into requirements.txt (for reproducible commits)
pip freeze > requirements.txt
echo "Virtual environment created in $(pwd)/.venv and requirements.txt updated."
