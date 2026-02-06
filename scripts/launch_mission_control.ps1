param(
  [string]$WorkDir = "C:\Users\codym\AgenticConsole"
)

Set-Location $WorkDir
python -m pip show chainlit > $null 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "chainlit not installed. Run: pip install chainlit"
  exit 1
}
chainlit run .\chainlit_app.py -w
