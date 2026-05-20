$env:PYTHONPATH = "$PSScriptRoot;$env:PYTHONPATH"
python -m freehold run @args
exit $LASTEXITCODE