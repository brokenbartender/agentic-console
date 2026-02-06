param(
  [string]$WorkDir = "C:\Users\codym\AgenticConsole"
)

Set-Location $WorkDir
python -c "import importlib; import sys; sys.exit(0 if importlib.util.find_spec('browser_use') else 1)"
if ($LASTEXITCODE -ne 0) {
  Write-Host "browser-use not installed. Run: pip install browser-use"
  exit 1
}

Write-Host "Launching browser-use desktop (if supported by your install)."
python -c "import browser_use; print('browser-use ready');"
