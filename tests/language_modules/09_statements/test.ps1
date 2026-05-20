$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 09_statements @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}