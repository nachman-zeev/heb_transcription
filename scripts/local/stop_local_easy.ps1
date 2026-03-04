$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$RuntimeDir = Join-Path $RepoRoot "data\local_runtime"
$ApiPidFile = Join-Path $RuntimeDir "api.pid"
$WorkerPidFile = Join-Path $RuntimeDir "worker.pid"
$WatchdogPidFile = Join-Path $RuntimeDir "watchdog.pid"
$ApiPattern = "uvicorn app.main:app --host 127.0.0.1 --port 8090"
$WorkerPattern = "worker.py --node-id local-cpu-node"
$WatchdogPattern = "idle_shutdown_watchdog.py"

function Stop-ByPidFile {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return }
  $pidRaw = (Get-Content $Path -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
  if (-not $pidRaw) { return }
  try {
    Stop-Process -Id ([int]$pidRaw) -Force -ErrorAction Stop
  } catch {}
  Remove-Item -Path $Path -Force -ErrorAction SilentlyContinue
}

function Stop-ByPattern {
  param([string]$Pattern)
  $procs = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -match $Pattern }
  foreach ($proc in $procs) {
    try {
      Stop-Process -Id ([int]$proc.ProcessId) -Force -ErrorAction Stop
    } catch {}
  }
}

Stop-ByPidFile $ApiPidFile
Stop-ByPidFile $WorkerPidFile
Stop-ByPidFile $WatchdogPidFile
Stop-ByPattern $ApiPattern
Stop-ByPattern $WorkerPattern
Stop-ByPattern $WatchdogPattern

Write-Output "Local system stopped."
