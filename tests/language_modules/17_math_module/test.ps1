$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 17_math_module @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}