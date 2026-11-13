@echo off
setlocal
where pwsh.exe >nul 2>nul
if errorlevel 1 (
    powershell.exe -NoProfile -File "%~dp0scripts\start.ps1" %*
) else (
    pwsh.exe -NoProfile -File "%~dp0scripts\start.ps1" %*
)
set "startupExit=%errorlevel%"
if not "%startupExit%"=="0" pause
exit /b %startupExit%
