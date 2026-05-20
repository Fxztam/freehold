$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 13_contract_blocks @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}