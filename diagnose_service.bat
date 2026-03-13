@echo off
:: Self-elevate to admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set EXE=C:\Users\Christof\PycharmProjects\BackupTool\dist\BackupTool\BackupToolService.exe
set LOG=C:\ProgramData\BackupTool\service_boot.log

echo === Stoppe alten Dienst ===
sc stop BackupToolSvc >nul 2>&1
timeout /t 2 /nobreak >nul
sc delete BackupToolSvc >nul 2>&1
timeout /t 2 /nobreak >nul

echo === Log leeren ===
if exist "%LOG%" del "%LOG%"

echo === Installiere Dienst ===
"%EXE%" install
timeout /t 1 /nobreak >nul

echo === Starte Dienst ===
sc start BackupToolSvc
timeout /t 5 /nobreak >nul

echo.
echo === Service Status ===
sc query BackupToolSvc

echo.
echo === service_boot.log ===
if exist "%LOG%" (
    type "%LOG%"
) else (
    echo Log wurde nicht erstellt!
)

echo.
pause
