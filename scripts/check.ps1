$ErrorActionPreference = 'Stop'
$workRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $workRoot '.venv\Scripts\python.exe'
Set-Location -LiteralPath $workRoot
& $pythonExe -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonExe -m ruff check backend training
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonExe -m ruff format --check backend training
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd --prefix frontend run build
exit $LASTEXITCODE
