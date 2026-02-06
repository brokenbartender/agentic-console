param(
  [string]$WorkDir = "C:\Users\codym\AgenticConsole"
)

Set-Location $WorkDir
python -m pip show nicegui > $null 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "nicegui not installed. Run: pip install nicegui"
  exit 1
}
python .\ui\nicegui_app.py
