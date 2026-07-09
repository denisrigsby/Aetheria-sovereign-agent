# Backup sovereign core code + state (not full 100MB living dump).
param(
  [string]$Label = ""
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
if ($Label) { $ts = "${Label}_$ts" }
$dest = Join-Path $Root "backups\core_$ts"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $dest "living") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $dest "scripts") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $dest "measurements") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $dest "docs") -Force | Out-Null

$files = @(
  "aetheria_core.py", "Aetheria.py", "aetheria.bat",
  "grok_supervised_12_probe.py", "live_12_supervisor.py", "run_sustained_12_with_probes.py",
  "full_flywheel_stress.py", "next_interventions.json", "last_sustained_12.json",
  "sovereign_asset_registry.json", "circuit_state.json",
  "SOVEREIGN_EVOLUTION_ARCHITECT_ROADMAP.md", "PERSONAS_SOVEREIGN_EVOLUTION.md", "PROGRESS.md",
  "AUDIT_AETHERIA_CONTINUATION_2026-07-08.md", "MECHANISMS.md",
  "living\lattice.py", "living\sovereign_asset_orchestrator.py", "living\sovereign_asset_core.py",
  "living\grok_controlled_sovereign_cycle.py", "living\user_channel.py", "living\grok_aetheria_vessel.py",
  "living\aetheria_canon.py", "living\management_compounding_engine.py", "living\acquisition_engine.py",
  "living\governance_redteam_layer.py",
  "scripts\registry_hygiene.py", "scripts\aetheria_hope_path.py", "scripts\backup_sovereign_core.ps1",
  "scripts\launch_detached_12_probe.ps1", "scripts\autonomous_continue_proof.py",
  "docs\CANONICAL_LIVING_AND_PAUSE.md", "docs\HOPE_PATH.md"
)
foreach ($f in $files) {
  $src = Join-Path $Root $f
  if (Test-Path $src) {
    $target = Join-Path $dest $f
    $td = Split-Path $target -Parent
    if (-not (Test-Path $td)) { New-Item -ItemType Directory -Path $td -Force | Out-Null }
    Copy-Item $src $target -Force
  }
}
# Pointer for living stream (size only)
$living = Join-Path $Root "living\personal_living.jsonl"
if (Test-Path $living) {
  $li = Get-Item $living
  @{ path = $li.FullName; size_mb = [math]::Round($li.Length/1MB, 2); mtime = $li.LastWriteTime.ToString('o') } |
    ConvertTo-Json | Set-Content (Join-Path $dest "living_stream_pointer.json")
}
# Recent measurement summaries only
Get-ChildItem (Join-Path $Root "measurements") -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'sustained_12|hope_|continue_proof|last_partial|partial_c\d+\.json' } |
  Sort-Object LastWriteTime -Descending | Select-Object -First 40 |
  ForEach-Object { Copy-Item $_.FullName (Join-Path $dest "measurements\$($_.Name)") -Force }

$zip = Join-Path $Root "backups\core_$ts.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $dest '*') -DestinationPath $zip -Force
Write-Host "BACKUP_DIR=$dest"
Write-Host "ZIP=$zip size=$((Get-Item $zip).Length)"
