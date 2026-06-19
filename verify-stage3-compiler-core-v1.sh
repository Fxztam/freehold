#!/bin/sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

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

if [ -z "$FREEHOLD_PROVER" ]; then
    export FREEHOLD_PROVER="none"
fi

if $PYTHON ./tools/verify_stage3_compiler_core_contracts.py --manifest ./artifacts/stage3/compiler_core_v1/manifest.json --out ./artifacts/stage3/compiler_core_v1/report; then
    exit 0
else
    exit_code=$?
    if [ "$exit_code" -eq 0 ]; then
        exit_code=1
    fi
    echo ""
    echo "Stage-3 compiler_core_v1 verify failed with exit code $exit_code."
    exit $exit_code
fi
