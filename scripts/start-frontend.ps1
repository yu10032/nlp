$ErrorActionPreference = 'Stop'
$workRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath "$workRoot\frontend"
& npm.cmd run dev
exit $LASTEXITCODE
