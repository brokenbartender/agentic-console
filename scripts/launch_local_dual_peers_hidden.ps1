param(
  [string]$Python = "python",
  [string]$AppPath = "C:\Users\codym\AgenticConsole\app.py",
  [int]$WebPortA = 8333,
  [int]$WebPortB = 8334,
  [int]$A2aPortA = 9451,
  [int]$A2aPortB = 9452,
  [string]$NameA = "local-a",
  [string]$NameB = "local-b"
)

function Start-AgentHidden($name, $webPort, $a2aPort, $peerName, $peerPort) {
  $cmd = 'Set-Location ''C:\\Users\\codym\\AgenticConsole''; ' +
         '$env:AGENTIC_DATA_DIR=''C:\\Users\\codym\\AgenticConsole\\data''; ' +
         '$env:AGENTIC_NODE_NAME=''{0}''; ' +
         '$env:AGENTIC_WEB_PORT=''{1}''; ' +
         '$env:AGENTIC_A2A_PORT=''{2}''; ' +
         '$env:AGENTIC_A2A_PEERS=''{3}:127.0.0.1:{4}''; ' +
         '& ''{5}'' ''{6}''' -f $name, $webPort, $a2aPort, $peerName, $peerPort, $Python, $AppPath
  Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    '-NoProfile','-ExecutionPolicy','Bypass','-Command',$cmd
  ) | Out-Null
}

Start-AgentHidden $NameA $WebPortA $A2aPortA $NameB $A2aPortB
Start-AgentHidden $NameB $WebPortB $A2aPortB $NameA $A2aPortA
