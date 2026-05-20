$env:PYTHONPATH = "$PSScriptRoot;$env:PYTHONPATH"
python -m freehold verify @args
exit $LASTEXITCODE