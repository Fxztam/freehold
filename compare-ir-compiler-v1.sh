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
TMP_ROOT=$(mktemp -d -t freehold-compare-ir-v1-XXXXXX)
TMP_PYTHON_ROOT="$TMP_ROOT/python"
TMP_GO_ROOT="$TMP_ROOT/go"
TMP_REPORT_ROOT="$TMP_ROOT/report"

echo "[mode] check-only; baselines are read-only"
echo "[mode] temporary output: $TMP_ROOT"

if ! $PYTHON ./tools/generate_compare_ir_samples.py --manifest "$MANIFEST" --python-root "$TMP_PYTHON_ROOT" --go-root "$TMP_GO_ROOT"; then
    echo "Compare-IR compiler V1 check failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

echo ""
echo "[check] Generated Python IR vs generated Go IR"
if ! $PYTHON ./tools/compare_ir_hashes.py --manifest "$MANIFEST" --python-root "$TMP_PYTHON_ROOT" --go-root "$TMP_GO_ROOT" --out "$TMP_REPORT_ROOT/generated-parity"; then
    echo "Compare-IR compiler V1 check failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

echo ""
echo "[check] Frozen Python IR baseline vs generated Python IR"
if ! $PYTHON ./tools/compare_ir_hashes.py --manifest "$MANIFEST" --python-root "$BASELINE_PYTHON_ROOT" --go-root "$TMP_PYTHON_ROOT" --out "$TMP_REPORT_ROOT/python-baseline"; then
    echo "Compare-IR compiler V1 check failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

echo ""
echo "[check] Frozen Go IR baseline vs generated Go IR"
if ! $PYTHON ./tools/compare_ir_hashes.py --manifest "$MANIFEST" --python-root "$BASELINE_GO_ROOT" --go-root "$TMP_GO_ROOT" --out "$TMP_REPORT_ROOT/go-baseline"; then
    echo "Compare-IR compiler V1 check failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

rm -rf "$TMP_ROOT"
exit 0
