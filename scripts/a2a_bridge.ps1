param(
  [string]$A2AApi = "http://127.0.0.1:8333/api/a2a",
  [string]$A2ASend = "",
  [string]$SharedSecret = "",
  [string]$CodexExecPath = "C:\nvm4w\nodejs\codex.ps1",
  [int]$PollSeconds = 2,
  [string]$SenderName = "",
  [string]$PeerName = "desktop",
  [string]$StateFile = "",
  [string]$LogFile = ""
)

$baseDir = Split-Path $PSScriptRoot -Parent
$dataDir = Join-Path $baseDir "data"
if (!(Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }

if (-not $StateFile) { $StateFile = Join-Path $dataDir "a2a_bridge_state.json" }
if (-not $LogFile) { $LogFile = Join-Path $dataDir "a2a_bridge.log" }

if (-not $SharedSecret) { $SharedSecret = $env:AGENTIC_A2A_SHARED_SECRET }
if (-not $SenderName) { $SenderName = if ($env:AGENTIC_NODE_NAME) { $env:AGENTIC_NODE_NAME } else { "laptop" } }

function Resolve-PeerUrl {
  param([string]$peer, [string]$peersEnv)
  if (-not $peersEnv) { return "" }
  $parts = $peersEnv.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  foreach ($p in $parts) {
    $kv = $p.Split("=")
    if ($kv.Length -eq 2 -and $kv[0].Trim() -eq $peer) {
      return "http://$($kv[1].Trim())/a2a"
    }
  }
  return ""
}

if (-not $A2ASend) {
  $A2ASend = Resolve-PeerUrl -peer $PeerName -peersEnv $env:AGENTIC_A2A_PEERS
}

if (-not $A2ASend) {
  $A2ASend = "http://127.0.0.1:9451/a2a"
}

function Load-State {
  if (Test-Path $StateFile) {
    try { return (Get-Content $StateFile -Raw | ConvertFrom-Json) } catch { }
  }
  return @{ last_ts = 0.0 }
}

function Save-State($state) {
  $state | ConvertTo-Json -Compress | Set-Content $StateFile -NoNewline
}

function Log-Line($text) {
  $line = "$(Get-Date -Format o) $text"
  Add-Content -Path $LogFile -Value $line
}

function Send-A2A($message) {
  $payload = @{ sender = $SenderName; receiver = $PeerName; message = $message; shared_secret = $SharedSecret } | ConvertTo-Json -Compress
  Invoke-RestMethod -Method Post -Uri $A2ASend -Body $payload -ContentType "application/json" | Out-Null
}

function Run-Codex($prompt) {
  try {
    $output = & $CodexExecPath exec $prompt 2>&1 | Out-String
    return $output.Trim()
  } catch {
    return "(codex exec failed)"
  }
}

$state = Load-State
Log-Line "A2A bridge started. Polling $A2AApi"

while ($true) {
  try {
    $msgs = Invoke-RestMethod -Method Get -Uri $A2AApi
    if ($msgs) {
      $new = $msgs | Where-Object { $_.timestamp -gt $state.last_ts } | Sort-Object -Property timestamp
      foreach ($m in $new) {
        # Respond to any message from the peer (receiver may be "remote" or "local")
        if ($m.sender -eq $PeerName) {
          Log-Line "INBOUND from $($m.sender): $($m.message)"
          $prompt = "Desktop message: $($m.message)`nRespond concisely."
          $reply = Run-Codex $prompt
          if ($reply) {
            Send-A2A $reply
            Log-Line "REPLIED to $PeerName: $reply"
          }
        }
        if ($m.timestamp -gt $state.last_ts) { $state.last_ts = $m.timestamp }
      }
      Save-State $state
    }
  } catch {
    Log-Line "ERROR: $($_.Exception.Message)"
  }
  Start-Sleep -Seconds $PollSeconds
}
