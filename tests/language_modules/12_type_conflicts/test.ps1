$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 12_type_conflicts @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}