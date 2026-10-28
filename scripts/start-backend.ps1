$ErrorActionPreference = 'Stop'
$workRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $workRoot
& "$workRoot\.venv\Scripts\python.exe" -m uvicorn ta_backend.main:app --reload --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
