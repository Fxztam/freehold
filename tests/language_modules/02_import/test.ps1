$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 02_import @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}