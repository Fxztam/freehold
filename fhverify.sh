#!/usr/bin/env bash
export PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd):$PYTHONPATH"
python3 -m freehold verify "$@"
