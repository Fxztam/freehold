#!/bin/sh
PYTHON="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
fi

$PYTHON ./tools/compare_semantic_diagnostics.py --expected ./tests/language_modules_02/expected_semantic_diagnostics.json --root ./tests/language_modules_02 --out ./artifacts/compare-semantic-diagnostics-02
