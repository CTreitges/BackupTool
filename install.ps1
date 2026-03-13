#Requires -Version 5.1
<#
.SYNOPSIS
    BackupTool Installer – installs the Windows service and tray autostart.
    Run by double-clicking or from any PowerShell window (self-elevates to Admin).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonExe  = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$MainScript = Join-Path $ScriptDir "main.py"

# ── Self-elevate if not admin ────────────────────────────────────────────────
function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "Requesting administrator privileges..." -ForegroundColor Yellow
    $args = "-ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Definition)`""
    Start-Process powershell -ArgumentList $args -Verb RunAs -Wait
    exit
}

# ── Helper ───────────────────────────────────────────────────────────────────
function Write-Step([string]$msg) {
    Write-Host "`n>> $msg" -ForegroundColor Cyan
}

function Write-OK([string]$msg) {
    Write-Host "   OK  $msg" -ForegroundColor Green
}

function Write-Fail([string]$msg) {
    Write-Host "   FAIL $msg" -ForegroundColor Red
    Read-Host "`nPress Enter to exit"
    exit 1
}

# ── Banner ───────────────────────────────────────────────────────────────────
Clear-Host
Write-Host "============================================" -ForegroundColor White
Write-Host "   BackupTool Installer" -ForegroundColor White
Write-Host "============================================" -ForegroundColor White
Write-Host "Install directory: $ScriptDir"

# ── 1. Python check ──────────────────────────────────────────────────────────
Write-Step "Checking Python environment"
if (-not (Test-Path $PythonExe)) {
    Write-Fail "Virtual environment not found at .venv\Scripts\python.exe`nRun: python -m venv .venv"
}
$pyver = & $PythonExe --version 2>&1
Write-OK $pyver

# ── 2. Install / update pip packages ────────────────────────────────────────
Write-Step "Installing Python dependencies"
$req = Join-Path $ScriptDir "requirements.txt"
if (Test-Path $req) {
    & $PythonExe -m pip install --quiet --upgrade -r $req
    if ($LASTEXITCODE -ne 0) { Write-Fail "pip install failed" }
    Write-OK "Dependencies installed"
} else {
    Write-Host "   SKIP requirements.txt not found" -ForegroundColor Yellow
}

# ── 3. Create ProgramData directory and default config ──────────────────────
Write-Step "Setting up configuration"
$progdata = "$env:ProgramData\BackupTool"
if (-not (Test-Path $progdata)) {
    New-Item -ItemType Directory -Path $progdata -Force | Out-Null
}
$cfgPath = "$progdata\config.json"
if (-not (Test-Path $cfgPath)) {
    & $PythonExe -c "
import sys; sys.path.insert(0,'$($ScriptDir -replace '\\','/')');
from config import load_config, save_config; save_config(load_config())
"
    Write-OK "Default config written to $cfgPath"
} else {
    Write-OK "Config already exists, keeping it"
}

# ── 4. Register project path in Python registry ──────────────────────────────
Write-Step "Registering Python module path"
& $PythonExe -c "
import sys; sys.path.insert(0, r'$ScriptDir')
from win32.lib import regutil
regutil.RegisterNamedPath('BackupTool', r'$ScriptDir')
print('  registered:', r'$ScriptDir')
"
if ($LASTEXITCODE -ne 0) { Write-Fail "Could not register Python path" }
Write-OK "Module path registered"

# ── 5. Remove old service if present ────────────────────────────────────────
Write-Step "Removing previous service installation (if any)"
$svcName = "BackupToolSvc"
$existing = Get-Service -Name $svcName -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.Status -eq "Running") {
        Stop-Service -Name $svcName -Force
        Start-Sleep -Seconds 2
    }
    & sc.exe delete $svcName | Out-Null
    Start-Sleep -Seconds 1
    Write-OK "Old service removed"
} else {
    Write-OK "No previous service found"
}

# ── 6. Install Windows service ───────────────────────────────────────────────
Write-Step "Installing Windows service"
& $PythonExe -c "
import sys; sys.path.insert(0, r'$ScriptDir')
import win32serviceutil, win32service
from service import BackupToolService
win32serviceutil.InstallService(
    pythonClassString='service.BackupToolService',
    serviceName=BackupToolService._svc_name_,
    displayName=BackupToolService._svc_display_name_,
    description=BackupToolService._svc_description_,
    startType=win32service.SERVICE_AUTO_START,
)
print('  service installed')
"
if ($LASTEXITCODE -ne 0) { Write-Fail "Service installation failed" }
Write-OK "Service '$svcName' installed (auto-start)"

# ── 7. Start the service ─────────────────────────────────────────────────────
Write-Step "Starting service"
try {
    Start-Service -Name $svcName
    Start-Sleep -Seconds 3
    $svc = Get-Service -Name $svcName
    if ($svc.Status -eq "Running") {
        Write-OK "Service is running"
    } else {
        Write-Host "   WARN Service status: $($svc.Status)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   WARN Could not start service: $_" -ForegroundColor Yellow
}

# ── 8. Tray autostart (current user) ────────────────────────────────────────
Write-Step "Registering tray app autostart"
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$trayCmd = "`"$PythonExe`" `"$MainScript`" tray"
Set-ItemProperty -Path $regPath -Name "BackupTool" -Value $trayCmd
Write-OK "Tray autostart registered"

# ── 9. Launch tray app now ───────────────────────────────────────────────────
Write-Step "Launching tray app"
Start-Process -FilePath $PythonExe -ArgumentList "`"$MainScript`" tray" -WindowStyle Hidden
Write-OK "Tray app started"

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor White
Write-Host "   Installation complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor White
Write-Host ""
Write-Host "  Service : BackupTool Sync Service (auto-start)"
Write-Host "  Config  : $cfgPath"
Write-Host "  Tray    : running in system tray"
Write-Host ""
Write-Host "  To configure folder pairs, right-click the tray icon -> Settings"
Write-Host ""
Read-Host "Press Enter to exit"
