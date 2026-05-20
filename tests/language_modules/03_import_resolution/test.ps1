$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 03_import_resolution @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}