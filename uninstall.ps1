#Requires -Version 5.1
<#
.SYNOPSIS
    BackupTool Uninstaller – stops and removes the service and autostart entries.
    Run by double-clicking or from any PowerShell window (self-elevates to Admin).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"

# ── Self-elevate ─────────────────────────────────────────────────────────────
function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "Requesting administrator privileges..." -ForegroundColor Yellow
    $argList = "-ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Definition)`""
    Start-Process powershell -ArgumentList $argList -Verb RunAs -Wait
    exit
}

function Write-Step([string]$msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK([string]$msg)   { Write-Host "   OK  $msg" -ForegroundColor Green }

Clear-Host
Write-Host "============================================" -ForegroundColor White
Write-Host "   BackupTool Uninstaller" -ForegroundColor White
Write-Host "============================================" -ForegroundColor White

$svcName = "BackupToolSvc"

# ── 1. Stop tray processes ───────────────────────────────────────────────────
Write-Step "Stopping tray app"
Get-Process -Name "python*" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*main.py tray*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Write-OK "Tray processes stopped"

# ── 2. Stop and remove service ───────────────────────────────────────────────
Write-Step "Removing Windows service"
$svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
if ($svc) {
    if ($svc.Status -eq "Running") {
        Stop-Service -Name $svcName -Force
        Start-Sleep -Seconds 2
    }
    & sc.exe delete $svcName | Out-Null
    Write-OK "Service removed"
} else {
    Write-OK "Service was not installed"
}

# ── 3. Remove autostart registry entry ──────────────────────────────────────
Write-Step "Removing tray autostart"
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
if (Get-ItemProperty -Path $regPath -Name "BackupTool" -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $regPath -Name "BackupTool"
    Write-OK "Autostart entry removed"
} else {
    Write-OK "No autostart entry found"
}

# ── 4. Remove registered Python path ────────────────────────────────────────
Write-Step "Removing Python module path"
if (Test-Path $PythonExe) {
    & $PythonExe -c "
import sys; sys.path.insert(0, r'$ScriptDir')
from win32.lib import regutil
try:
    regutil.UnregisterNamedPath('BackupTool')
    print('  unregistered')
except Exception as e:
    print('  skipped:', e)
" 2>$null
}
Write-OK "Module path unregistered"

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor White
Write-Host "   BackupTool has been uninstalled." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor White
Write-Host ""
Write-Host "  Config and logs in C:\ProgramData\BackupTool were kept."
Write-Host "  Delete that folder manually if you want a clean removal."
Write-Host ""
Read-Host "Press Enter to exit"
