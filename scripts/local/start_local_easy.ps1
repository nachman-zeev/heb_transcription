$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BackendDir = Join-Path $RepoRoot "backend"
$RuntimeDir = Join-Path $RepoRoot "data\local_runtime"
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

$Port = 8090
$ApiPidFile = Join-Path $RuntimeDir "api.pid"
$WorkerPidFile = Join-Path $RuntimeDir "worker.pid"
$WatchdogPidFile = Join-Path $RuntimeDir "watchdog.pid"
$ApiPattern = "uvicorn app.main:app --host 127.0.0.1 --port $Port"
$WorkerPattern = "worker.py --node-id local-cpu-node"
$WatchdogPattern = "idle_shutdown_watchdog.py"
$WatchdogScript = Join-Path $RepoRoot "scripts\local\idle_shutdown_watchdog.py"
$DbPath = Join-Path $BackendDir "data\user_local.db"
$IdleMinutes = 5
if ($env:LOCAL_IDLE_SHUTDOWN_MINUTES) {
  try {
    $IdleMinutes = [int]$env:LOCAL_IDLE_SHUTDOWN_MINUTES
  } catch {}
}
$IdleMinutes = [Math]::Max(1, $IdleMinutes)

function Get-RunningPidFromFile {
  param([string]$Path, [string]$Pattern)
  if (-not (Test-Path $Path)) { return $null }
  $pidRaw = (Get-Content $Path -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
  if (-not $pidRaw) { return $null }
  try {
    $procId = [int]$pidRaw
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" |
      Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -match $Pattern } |
      Select-Object -First 1
    if ($proc) {
      return $procId
    }
    return $null
  } catch {
    return $null
  }
}

function Find-ExistingProcessId {
  param([string]$Pattern)
  $proc = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -match $Pattern } |
    Select-Object -First 1
  if ($proc) { return [int]$proc.ProcessId }
  return $null
}

function Ensure-ManagedProcess {
  param(
    [string]$PidFile,
    [string]$Pattern,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory = $BackendDir
  )

  $runningPid = Get-RunningPidFromFile -Path $PidFile -Pattern $Pattern
  if ($runningPid) { return $runningPid }

  $existingPid = Find-ExistingProcessId -Pattern $Pattern
  if ($existingPid) {
    Set-Content -Path $PidFile -Value $existingPid -Encoding ascii
    return $existingPid
  }

  $proc = Start-Process -FilePath "python" -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru
  Start-Sleep -Milliseconds 350
  $started = Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)" |
    Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -match $Pattern } |
    Select-Object -First 1
  if (-not $started) {
    throw "Failed to start managed process for pattern: $Pattern"
  }
  Set-Content -Path $PidFile -Value $proc.Id -Encoding ascii
  return $proc.Id
}

$env:APP_ENV = "prod"
$env:DB_URL = "sqlite:///./data/user_local.db"
$env:PRIMARY_MODEL_ID = "ivrit-ai/whisper-large-v3"
$env:ASR_BATCH_SIZE_CPU = "1"
$env:MAX_PARALLEL_WORKERS_CPU = "1"

$null = Ensure-ManagedProcess -PidFile $ApiPidFile -Pattern $ApiPattern -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port")
$null = Ensure-ManagedProcess -PidFile $WorkerPidFile -Pattern $WorkerPattern -ArgumentList @("worker.py", "--node-id", "local-cpu-node")
$null = Ensure-ManagedProcess -PidFile $WatchdogPidFile -Pattern $WatchdogPattern -ArgumentList @(
  $WatchdogScript,
  "--db-path", $DbPath,
  "--api-pid-file", $ApiPidFile,
  "--worker-pid-file", $WorkerPidFile,
  "--watchdog-pid-file", $WatchdogPidFile,
  "--idle-minutes", "$IdleMinutes",
  "--check-seconds", "15"
) -WorkingDirectory $RepoRoot

Start-Sleep -Seconds 1
Start-Process "http://127.0.0.1:$Port"
Write-Output "Local system started. Open: http://127.0.0.1:$Port (auto-shutdown idle: $IdleMinutes min)"
