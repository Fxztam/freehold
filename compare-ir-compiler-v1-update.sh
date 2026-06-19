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

MANIFEST="./artifacts/fhir-samples/compiler_v1/manifest.json"
BASELINE_PYTHON_ROOT="./artifacts/compare-ir/compiler_v1/python"
BASELINE_GO_ROOT="./artifacts/compare-ir/compiler_v1/go"
REPORT_ROOT="./artifacts/compare-ir/compiler_v1/report"

echo "[mode] update-baseline; writing compiler V1 Compare-IR artifacts"

$PYTHON ./tools/generate_compare_ir_samples.py --manifest "$MANIFEST" --python-root "$BASELINE_PYTHON_ROOT" --go-root "$BASELINE_GO_ROOT" || exit 1
$PYTHON ./tools/compare_ir_hashes.py --manifest "$MANIFEST" --python-root "$BASELINE_PYTHON_ROOT" --go-root "$BASELINE_GO_ROOT" --out "$REPORT_ROOT" || exit 1

exit 0
