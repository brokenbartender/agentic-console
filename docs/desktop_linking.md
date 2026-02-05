# Desktop Linking: Codex Workstation <-> CODYDESKTOP

## Goal (Plain English)
Connect the two Windows machines so your Codex CLI can run commands on the desktop, copy files, and use the desktop's compute from this machine. This makes the system feel like one unified environment.

## Prerequisites
- Both devices are on the same Tailscale account.
- You have local admin access on CODYDESKTOP.

## Tailscale IPs
- CODYDESKTOP: `100.111.161.110`
- This machine (codex-work): `100.98.190.75`

## Step 1: Enable SSH on CODYDESKTOP (run on CODYDESKTOP as Admin)
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

## Step 2: Test SSH from this machine
```powershell
ssh codym@100.111.161.110
```
When prompted:
- Type `yes` to trust the host key.
- Enter your Windows password for `codym` on CODYDESKTOP.

## Step 3: Add SSH aliases (this machine)
Your SSH config:
```
Host codydesktop
  HostName 100.111.161.110
  User codym

Host codex-work
  HostName 100.98.190.75
  User codym
```

PowerShell profile helpers:
```powershell
function desk { ssh codydesktop @args }
function work { ssh codex-work @args }
function deskcopy { scp @args }
```

## Step 4: Quick sanity checks
```powershell
desk hostname
desk dir C:\Users\codym
```

## If SSH times out
SSH timeout means port 22 is blocked or sshd isn’t running. Re-run the Step 1 commands on CODYDESKTOP.

## Optional: File Sharing (SMB)
On CODYDESKTOP (Admin):
```powershell
New-Item -ItemType Directory -Path C:\Share -Force
New-SmbShare -Name Share -Path C:\Share -FullAccess "codym"
Enable-NetFirewallRule -DisplayGroup "File and Printer Sharing"
```
From this machine:
```
\\10.0.0.124\Share
```

## Status
- Tailscale: installed and logged in on both machines.
- SSH: pending until CODYDESKTOP runs Step 1.
