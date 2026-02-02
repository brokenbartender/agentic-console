$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip
python -m pip install pyinstaller
pyinstaller --name AgenticConsole --onefile app.py
Write-Host "Build complete. See dist/AgenticConsole.exe"
