$env:PYTHONPATH = "$PSScriptRoot;$env:PYTHONPATH"
python -m freehold ast @args
exit $LASTEXITCODE