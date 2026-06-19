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

MANIFEST="./artifacts/source-map/compiler_v1/manifest.json"
TMP_ROOT=$(mktemp -d -t freehold-compare-sm-v1-XXXXXX)
TMP_PYTHON_ROOT="$TMP_ROOT/python"
TMP_GO_ROOT="$TMP_ROOT/go"
TMP_REPORT_ROOT="$TMP_ROOT/report"

echo "[mode] source-map check-only; baselines are read-only"
echo "[mode] temporary output: $TMP_ROOT"

if ! $PYTHON ./tools/generate_source_map_samples.py --manifest "$MANIFEST" --python-root "$TMP_PYTHON_ROOT" --go-root "$TMP_GO_ROOT"; then
    echo "Source-map generation failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

echo ""
echo "[check] Generated Python source-map vs generated Go source-map (contract projection)"
if ! $PYTHON ./tools/compare_source_maps.py --manifest "$MANIFEST" --python-root "$TMP_PYTHON_ROOT" --go-root "$TMP_GO_ROOT" --out "$TMP_REPORT_ROOT/generated-parity"; then
    echo "Source-map compiler V1 check failed."
    echo "Temporary artifacts kept for inspection: $TMP_ROOT"
    exit 1
fi

rm -rf "$TMP_ROOT"
exit 0
