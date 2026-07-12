# Sanitized public demo launcher (control plane only).
# Does not start long-horizon plant. Does not load private companion/G4.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "scripts\demo_local_smoke.py")) {
  Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
  Set-Location ..
}
Write-Host "Aetheria sanitized demo — public control plane" -ForegroundColor Cyan
Write-Host "Workspace: $(Get-Location)"
$py = "python"
if (Test-Path ".\.venv\Scripts\python.exe") { $py = ".\.venv\Scripts\python.exe" }
& $py -u scripts\demo_local_smoke.py
exit $LASTEXITCODE
