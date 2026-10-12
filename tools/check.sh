#!/usr/bin/env bash
# Run the repository's daily checks without hardware access.
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$task_root"

uv run --locked ruff format --check src tests tools
uv run --locked ruff check src tests tools
for task_script in tools/*.sh; do
  bash -n "$task_script"
done
uv run --locked pytest -q
