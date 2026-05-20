$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 05_records @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}