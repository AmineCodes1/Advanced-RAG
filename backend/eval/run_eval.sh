#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
exec uv run --extra eval python eval/run_ragas.py "$@"
