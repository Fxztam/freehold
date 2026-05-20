$env:PYTHONPATH = "$PSScriptRoot;$env:PYTHONPATH"
python (Join-Path $PSScriptRoot "tools/test_steps.py") @args
exit $LASTEXITCODE