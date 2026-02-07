$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python not found on PATH"
    exit 1
}

Write-Host "Running smoke checks"

python (Join-Path $root "runtime\run.py") agent status
python (Join-Path $root "runtime\run.py") agent tools
python (Join-Path $root "runtime\run.py") memory show

Write-Host "Smoke checks complete"
