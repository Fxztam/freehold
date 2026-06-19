#!/bin/sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PYTHON="python"
if [ -f "../.venv/bin/python" ]; then
    PYTHON="../.venv/bin/python"
elif [ -f "./.venv/bin/python" ]; then
    PYTHON="./.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
fi

export PYTHONPATH="..:$PYTHONPATH"

echo "[1/2] Verifying Freehold contractual correctness..."
$PYTHON -m freehold verify App.fh --prover z3 || exit 1

echo "[2/2] Generating and compiling native executable in ./bin..."
$PYTHON -m freehold build-exe App.fh --output-dir ./bin --executable-name my_app || exit 1

echo ""
echo "[OK] Build completed successfully!"
echo "Run the binary with: ./bin/my_app"
exit 0
