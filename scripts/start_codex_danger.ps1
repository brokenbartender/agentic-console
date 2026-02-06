param(
  [string]$CodexCmd = "codex danger-full-access"
)

Write-Host "Starting Codex with full access..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -Command $CodexCmd
