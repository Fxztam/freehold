$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 01_core @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}