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

## If SSH says "Permission denied"
On CODYDESKTOP (Admin PowerShell):
```powershell
notepad "C:\ProgramData\ssh\sshd_config"
```
Ensure these lines exist (add if missing):
```
PasswordAuthentication yes
PubkeyAuthentication yes
```
Save, then restart SSH:
```powershell
Restart-Service sshd
```

## Troubleshooting Log (What we tried + current errors)
- Tailscale installed and logged in on both machines.
- Tailscale IPs:
  - CODYDESKTOP: `100.111.161.110`
  - This machine: `100.98.190.75`
- SSH attempt from this machine:
  - Host key accepted.
  - Password prompt appears, typing is invisible (normal SSH behavior).
  - Error observed: `Permission denied, please try again.` then `Connection reset by 100.111.161.110 port 22`.
- Likely causes:
  - Wrong Windows password for `CODYDESKTOP\codym`, or
  - `PasswordAuthentication` disabled in `sshd_config`.

## What to check on CODYDESKTOP
1. Confirm the correct Windows password for user `codym`.
2. Ensure `sshd_config` allows password auth:
   ```
   PasswordAuthentication yes
   PubkeyAuthentication yes
   ```
3. Restart SSH service:
   ```powershell
   Restart-Service sshd
   ```

## If password auth continues failing (key-based login)
1. On this machine:
   ```powershell
   ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\codydesktop -N ""
   ```
2. Copy the public key to the desktop (one-time):
   ```powershell
   type $env:USERPROFILE\.ssh\codydesktop.pub | ssh codym@100.111.161.110 "powershell -Command \"New-Item -ItemType Directory -Path $env:USERPROFILE\.ssh -Force; Add-Content -Path $env:USERPROFILE\.ssh\authorized_keys -Value (Get-Content -Raw)\""
   ```
3. Then connect with:
   ```powershell
   ssh -i $env:USERPROFILE\.ssh\codydesktop codym@100.111.161.110
   ```

## Windows Admin Account Key Auth Fix
If your user is in the local Administrators group, OpenSSH on Windows ignores `C:\Users\<you>\.ssh\authorized_keys` and instead uses:
`C:\ProgramData\ssh\administrators_authorized_keys`

Ensure the file exists and permissions are locked down:
```powershell
New-Item -ItemType File -Path C:\ProgramData\ssh\administrators_authorized_keys -Force
icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r
icacls C:\ProgramData\ssh\administrators_authorized_keys /grant "Administrators:F"
icacls C:\ProgramData\ssh\administrators_authorized_keys /grant "SYSTEM:F"
```
Then append your public key to that file (from codex-work):
```powershell
type $env:USERPROFILE\.ssh\codydesktop.pub | ssh codym@100.111.161.110 "powershell -Command \"Add-Content -Path C:\ProgramData\ssh\administrators_authorized_keys -Value (Get-Content -Raw)\""
```
Restart SSH after edits:
```powershell
Restart-Service sshd
```

## End-to-end test (run on codex-work)
After adding the key and restarting `sshd`, verify the connection from codex-work:
```powershell
ssh -i $env:USERPROFILE\.ssh\codydesktop codym@100.111.161.110
```
If it fails, capture the exact error text and re-check:
- The key line exists in `C:\ProgramData\ssh\administrators_authorized_keys`
- The file ACLs allow only `Administrators` and `SYSTEM`
- `sshd` is running and port 22 is listening

### Current public key (generated on codex-work)
Use this exact key on CODYDESKTOP:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKnHxexuAbVPO3dp9c/gzXKRtv+NdK+m8YULemImsDb6 codym@Work
```

### Add key on CODYDESKTOP (PowerShell)
```powershell
New-Item -ItemType Directory -Path $env:USERPROFILE\.ssh -Force
Add-Content -Path $env:USERPROFILE\.ssh\authorized_keys -Value 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKnHxexuAbVPO3dp9c/gzXKRtv+NdK+m8YULemImsDb6 codym@Work'
```

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
SSH timeout means port 22 is blocked or sshd isn't running. Re-run the Step 1 commands on CODYDESKTOP.

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

