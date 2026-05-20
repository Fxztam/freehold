$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 11_errors_results @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}