# Detached long-horizon watchdog process.
# Monitors long_horizon_supervisor; relaunches on death/stall; notifies only as needed.
param(
  [double]$IntervalSec = 60
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
New-Item -ItemType Directory -Path logs, measurements -Force | Out-Null

$pidFile = Join-Path $Root "measurements\watchdog.pid"
if (Test-Path $pidFile) {
  $old = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($old -match '^\d+$') {
    $p = Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue
    if ($p) {
      Write-Host "Stopping previous watchdog PID $old"
      Stop-Process -Id ([int]$old) -Force -ErrorAction SilentlyContinue
    }
  }
}
if (Test-Path (Join-Path $Root "measurements\watchdog_STOP")) {
  Remove-Item (Join-Path $Root "measurements\watchdog_STOP") -Force
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "logs\lh_watchdog_launch_$ts.log"
$proc = Start-Process -FilePath "python" -ArgumentList @(
  "-u", "scripts\lh_watchdog.py", "--interval-sec", "$IntervalSec"
) -WorkingDirectory $Root -RedirectStandardOutput $out -RedirectStandardError "$out.err" -WindowStyle Hidden -PassThru

@"
launched: $(Get-Date -Format o)
watchdog_pid: $($proc.Id)
interval_sec: $IntervalSec
status: measurements\watchdog_status.json
notify: measurements\NOTIFY_USER.md
stop: echo stop > measurements\watchdog_STOP
"@ | Set-Content "logs\lh_watchdog_launch_$ts.meta.txt"

Write-Host "WATCHDOG_PID=$($proc.Id)"
Write-Host "STATUS=measurements\watchdog_status.json"
Write-Host "NOTIFY=measurements\NOTIFY_USER.md"
Write-Host "LOG=$out"
