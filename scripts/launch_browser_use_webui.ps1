param(
  [string]$WorkDir = "C:\Users\codym\AgenticConsole"
)

Set-Location $WorkDir
python -c "import importlib; import sys; sys.exit(0 if importlib.util.find_spec('browser_use') else 1)"
if ($LASTEXITCODE -ne 0) {
  Write-Host "browser-use not installed. Run: pip install browser-use"
  exit 1
}

# Attempt to launch browser-use web UI if available
python -c "import browser_use, sys; print('browser-use installed')"
Write-Host "If browser-use web UI is installed, start it via its CLI or module."
