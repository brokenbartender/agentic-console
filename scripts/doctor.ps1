$ErrorActionPreference = "Stop"

Write-Host "Agentic Console Doctor"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

Write-Host "Root: $root"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python not found on PATH"
    exit 1
}

python -V
pip -V

$dataDir = Join-Path $root "data"
$logFile = Join-Path $dataDir "agentic.log"
$memoryDb = Join-Path $dataDir "memory.db"

if (-not (Test-Path $dataDir)) {
    Write-Host "Data directory missing: $dataDir"
} else {
    Write-Host "Data directory ok: $dataDir"
}

if (Test-Path $logFile) {
    Write-Host "Log file ok: $logFile"
} else {
    Write-Host "Log file missing: $logFile"
}

if (Test-Path $memoryDb) {
    Write-Host "Memory DB ok: $memoryDb"
} else {
    Write-Host "Memory DB missing: $memoryDb"
}

$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Write-Host ".env present"
} else {
    Write-Host ".env not found"
}

Write-Host "Doctor finished"
