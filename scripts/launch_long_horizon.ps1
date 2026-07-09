# Launch long-horizon Aetheria supervisor as a detached process.
# Survives reauth; survives closing the terminal if -WindowStyle Hidden.
param(
  [int]$Cycles = 2,
  [double]$IntervalMin = 30,
  [int]$MaxTicks = 48,
  [int]$BackupEvery = 4,
  [switch]$Once
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
New-Item -ItemType Directory -Path logs, measurements -Force | Out-Null

# Stop previous if pid file points to live process
$pidFile = Join-Path $Root "measurements\long_horizon.pid"
if (Test-Path $pidFile) {
  $old = Get-Content $pidFile -ErrorAction SilentlyContinue
  if ($old) {
    $p = Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue
    if ($p) {
      Write-Host "Stopping previous long-horizon PID $old"
      Stop-Process -Id ([int]$old) -Force -ErrorAction SilentlyContinue
    }
  }
}
if (Test-Path (Join-Path $Root "measurements\long_horizon_STOP")) {
  Remove-Item (Join-Path $Root "measurements\long_horizon_STOP") -Force
}

$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"

$argsList = @(
  "-u", "scripts\long_horizon_supervisor.py",
  "--cycles", "$Cycles",
  "--interval-min", "$IntervalMin",
  "--max-ticks", "$MaxTicks",
  "--backup-every", "$BackupEvery"
)
if ($Once) { $argsList += "--once" }

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "logs\long_horizon_launch_$ts.log"
$proc = Start-Process -FilePath "python" -ArgumentList $argsList `
  -WorkingDirectory $Root `
  -RedirectStandardOutput $out `
  -RedirectStandardError "$out.err" `
  -WindowStyle Hidden `
  -PassThru

@"
launched: $(Get-Date -Format o)
supervisor_pid: $($proc.Id)
cycles_per_tick: $Cycles
interval_min: $IntervalMin
max_ticks: $MaxTicks
launch_log: $out
state: measurements\long_horizon_state.json
hope: measurements\hope_status.json
stop: echo stop > measurements\long_horizon_STOP
handoff: HANDOFF_NEXT_SESSION.md
NOTE: Independent of interactive sessions; survives terminal close when launched hidden.
"@ | Set-Content "logs\long_horizon_launch_$ts.meta.txt"

Write-Host "LONG_HORIZON_PID=$($proc.Id)"
Write-Host "STATE=measurements\long_horizon_state.json"
Write-Host "STOP=echo stop > measurements\long_horizon_STOP"
Write-Host "LOG=$out"
