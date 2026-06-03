#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
. .venv/bin/activate
pip install -r apps/api/requirements.txt
python3 scripts/seed_demo.py
uvicorn platformops.main:app --app-dir apps/api --reload
