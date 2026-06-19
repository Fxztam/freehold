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

$PYTHON ./tools/generate_compare_ir_samples.py --manifest ./artifacts/fhir-samples/manifest.json --python-root ./artifacts/compare-ir/python --go-root ./artifacts/compare-ir/go || exit 1
$PYTHON ./tools/compare_ir_hashes.py --manifest ./artifacts/fhir-samples/manifest.json --python-root ./artifacts/compare-ir/python --go-root ./artifacts/compare-ir/go --out ./artifacts/compare-ir/report || exit 1

exit 0
