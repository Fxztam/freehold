$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 16_control_flow_edges @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}