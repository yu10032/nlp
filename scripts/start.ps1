param(
    [switch]$NoBrowser,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$workRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$logRoot = Join-Path $workRoot 'logs'
$frontendUrl = 'http://127.0.0.1:5173'
$services = @(
    [pscustomobject]@{ Name = 'backend'; Port = 8000; Url = 'http://127.0.0.1:8000/api/v1/health'; Ready = $false; Process = $null; LastError = '' },
    [pscustomobject]@{ Name = 'frontend'; Port = 5173; Url = $frontendUrl; Ready = $false; Process = $null; LastError = '' }
)

if ($Stop) {
    # Only stop wrappers launched with this project's exact script paths.
    $wrappers = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe' OR Name = 'pwsh.exe'"
    foreach ($service in $services) {
        $scriptPath = Join-Path $PSScriptRoot "start-$($service.Name).ps1"
        $fileArgument = '-File\s+"' + [regex]::Escape($scriptPath) + '"(?:\s|$)'
        foreach ($wrapper in $wrappers) {
            if ($wrapper.CommandLine -match $fileArgument) {
                & taskkill.exe /PID $wrapper.ProcessId /T /F | Out-Null
                if ($LASTEXITCODE -ne 0) { throw "Could not stop $($service.Name), PID $($wrapper.ProcessId)." }
                Write-Host "Stopped $($service.Name)."
            }
        }
    }
    exit 0
}

function Test-ServiceReady($service) {
    try {
        $response = Invoke-WebRequest -Uri $service.Url -UseBasicParsing -TimeoutSec 2
        if ($service.Name -eq 'backend') {
            $service.Ready = ($response.Content | ConvertFrom-Json).status -eq 'ok'
        } else {
            $service.Ready = $response.Content.Contains('/src/main.ts')
        }
        if (-not $service.Ready) { $service.LastError = 'Unexpected response from this port.' }
    } catch {
        # Connection failures are expected during startup; retain the reason for a timeout.
        $service.LastError = $_.Exception.Message
        $service.Ready = $false
    }
    return $service.Ready
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$shellExecutable = Join-Path $PSHOME 'pwsh.exe'
if (-not (Test-Path -LiteralPath $shellExecutable)) {
    $shellExecutable = Join-Path $PSHOME 'powershell.exe'
}

foreach ($service in $services) {
    if (Test-ServiceReady $service) {
        Write-Host "Reusing $($service.Name): $($service.Url)"
        continue
    }
    if (Get-NetTCPConnection -State Listen -LocalPort $service.Port -ErrorAction SilentlyContinue) {
        throw "Port $($service.Port) is occupied or still starting. Check $($service.Url) before trying again."
    }
    $scriptPath = Join-Path $PSScriptRoot "start-$($service.Name).ps1"
    $service.Process = Start-Process -FilePath $shellExecutable -ArgumentList @('-NoProfile', '-File', ('"{0}"' -f $scriptPath)) `
        -WorkingDirectory $workRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logRoot "$($service.Name).out.log") `
        -RedirectStandardError (Join-Path $logRoot "$($service.Name).err.log")
    Write-Host "Starting $($service.Name); logs: $logRoot"
}

$deadline = (Get-Date).AddSeconds(120)
while ($services.Where({ -not $_.Ready }).Count -gt 0) {
    foreach ($service in $services.Where({ -not $_.Ready })) {
        if (Test-ServiceReady $service) {
            Write-Host "Ready: $($service.Url)"
        } elseif ($service.Process -and $service.Process.HasExited) {
            throw "$($service.Name) exited. See $(Join-Path $logRoot "$($service.Name).err.log")."
        }
    }
    if ($services.Where({ -not $_.Ready }).Count -eq 0) { break }
    if ((Get-Date) -ge $deadline) {
        $pending = $services.Where({ -not $_.Ready }) | ForEach-Object { "$($_.Url): $($_.LastError)" }
        throw "Startup timed out. $($pending -join '; ') Logs: $logRoot"
    }
    Start-Sleep -Milliseconds 500
}

Write-Host "Workbench ready: $frontendUrl"
Write-Host 'Services started here run in the background; stop.cmd stops those services.'
if (-not $NoBrowser) { Start-Process $frontendUrl }
