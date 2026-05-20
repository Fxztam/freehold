$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
Push-Location $ProjectRoot
try {
    python -m freehold test-language --module 14_comments_whitespace @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}