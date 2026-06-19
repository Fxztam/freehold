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

MANIFEST="./artifacts/fhir-samples/compiler_v1_stage2/manifest.json"
TMP_ROOT=$(mktemp -d -t freehold-compare-ir-stage2-XXXXXX)
TMP_PYTHON_ROOT="$TMP_ROOT/python"
TMP_GO_ROOT="$TMP_ROOT/go"
TMP_REPORT_ROOT="$TMP_ROOT/report"

echo "[mode] stage2 check-only; baselines are read-only"
echo "[mode] temporary output: $TMP_ROOT"

if ! $PYTHON ./tools/generate_compare_ir_samples.py --manifest "$MANIFEST" --python-root "$TMP_PYTHON_ROOT" --go-root "$TMP_GO_ROOT"; then
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

echo ""
echo "[check] Stage 2 generated Python IR vs generated Go IR (semantic compiler-contract projection)"
if ! $PYTHON ./tools/compare_ir_hashes.py --comparison semantic --manifest "$MANIFEST" --python-root "$TMP_PYTHON_ROOT" --go-root "$TMP_GO_ROOT" --out "$TMP_REPORT_ROOT/generated-parity-semantic"; then
    echo "Compare-IR compiler V1 Stage 2 check failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

echo ""
echo "[check] Stage 2 generated Python IR vs generated Go IR (full JSON hash)"
if ! $PYTHON ./tools/compare_ir_hashes.py --comparison full --manifest "$MANIFEST" --python-root "$TMP_PYTHON_ROOT" --go-root "$TMP_GO_ROOT" --out "$TMP_REPORT_ROOT/generated-parity-full"; then
    echo "Compare-IR compiler V1 Stage 2 check failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

echo ""
echo "[check] Stage 2 Go project structure contracts"
if ! $PYTHON ./tools/verify_stage2_go_project_contracts.py --manifest "$MANIFEST" --out "$TMP_REPORT_ROOT/go-project-contracts"; then
    echo "Compare-IR compiler V1 Stage 2 check failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

rm -rf "$TMP_ROOT"
exit 0
