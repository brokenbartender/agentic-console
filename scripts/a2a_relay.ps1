param(
  [string]$LogFile = "",
  [string]$StateFile = "",
  [int]$PollSeconds = 2
)

$baseDir = Split-Path $PSScriptRoot -Parent
$dataDir = Join-Path $baseDir "data"
if (!(Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }

if (-not $LogFile) { $LogFile = Join-Path $dataDir "a2a_bridge.log" }
if (-not $StateFile) { $StateFile = Join-Path $dataDir "a2a_relay_state.json" }

function Load-State {
  if (Test-Path $StateFile) {
    try { return (Get-Content $StateFile -Raw | ConvertFrom-Json) } catch { }
  }
  return @{ last_line = 0 }
}

function Save-State($state) {
  $state | ConvertTo-Json -Compress | Set-Content $StateFile -NoNewline
}

$state = Load-State

while ($true) {
  try {
    if (Test-Path $LogFile) {
      $lines = Get-Content $LogFile
      $count = $lines.Count
      if ($count -gt $state.last_line) {
        $new = $lines[$state.last_line..($count-1)]
        foreach ($line in $new) {
          if ($line -match "INBOUND from ") {
            Write-Output $line
          }
        }
        $state.last_line = $count
        Save-State $state
      }
    }
  } catch {}
  Start-Sleep -Seconds $PollSeconds
}
