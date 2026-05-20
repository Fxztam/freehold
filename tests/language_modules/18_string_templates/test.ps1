$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 18_string_templates @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}