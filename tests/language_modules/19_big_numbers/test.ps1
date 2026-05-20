$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 19_big_numbers @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
