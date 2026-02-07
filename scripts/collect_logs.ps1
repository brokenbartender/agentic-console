$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dataDir = Join-Path $root "data"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $root "tmp\support_$timestamp"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$files = @(
    Join-Path $dataDir "agentic.log",
    Join-Path $dataDir "memory.db",
    Join-Path $root ".env"
)

foreach ($f in $files) {
    if (Test-Path $f) {
        Copy-Item $f -Destination $outDir -Force
    }
}

$runs = Join-Path $dataDir "runs"
if (Test-Path $runs) {
    Copy-Item $runs -Destination $outDir -Recurse -Force
}

$zip = "$outDir.zip"
if (Test-Path $zip) {
    Remove-Item $zip -Force
}
Compress-Archive -Path $outDir\* -DestinationPath $zip

Write-Host "Collected logs at: $zip"
