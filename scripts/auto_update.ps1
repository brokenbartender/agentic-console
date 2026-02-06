param(
  [int]$IntervalMinutes = 2,
  [string]$AgenticConsolePath = "C:\Users\codym\AgenticConsole",
  [string]$ControlPlanePath = "C:\Users\codym\agentic-control-plane",
  [string]$CodexControlStackPath = "C:\Users\codym\codex-control-stack",
  [string]$LogFile = "C:\Users\codym\AgenticConsole\data\auto_update.log"
)

function Log-Line($text) {
  $line = "$(Get-Date -Format o) $text"
  Add-Content -Path $LogFile -Value $line
}

function Pull-Repo($path) {
  if (!(Test-Path $path)) {
    Log-Line "SKIP (missing): $path"
    return $false
  }
  $before = (git -C $path rev-parse HEAD) 2>$null
  git -C $path pull 2>&1 | Out-String | ForEach-Object { $_.Trim() } | ForEach-Object { if ($_) { Log-Line "git pull [$path] $($_)" } }
  $after = (git -C $path rev-parse HEAD) 2>$null
  return ($before -ne $after)
}

function Restart-AgenticConsole($path) {
  try {
    $procs = Get-Process | Where-Object { $_.MainWindowTitle -like "*Agentic Console*" }
    foreach ($p in $procs) {
      try { $p.CloseMainWindow() | Out-Null } catch {}
      Start-Sleep -Seconds 1
      if (!$p.HasExited) { try { Stop-Process -Id $p.Id -Force } catch {} }
    }
  } catch {}

  Start-Process powershell -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-Command',"cd $path; python app.py") | Out-Null
  Log-Line "Agentic Console restarted"
}

function Restart-A2ATasks {
  try { schtasks /Run /TN "AgenticA2ABridge" | Out-Null } catch {}
  try { schtasks /Run /TN "AgenticA2ARelay" | Out-Null } catch {}
  Log-Line "A2A tasks triggered"
}

Log-Line "Auto-update tick (interval=${IntervalMinutes}m)"
$acChanged = Pull-Repo $AgenticConsolePath
$cpChanged = Pull-Repo $ControlPlanePath
$ccsChanged = Pull-Repo $CodexControlStackPath

if ($acChanged) {
  Restart-AgenticConsole $AgenticConsolePath
  Restart-A2ATasks
}

if ($cpChanged -or $ccsChanged) {
  Log-Line "Other repo changes detected (control-plane or codex-control-stack)"
}
