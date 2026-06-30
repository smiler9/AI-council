#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR/backend"
../.venv/bin/python -m pytest

cd "$ROOT_DIR/frontend"
npm run build
