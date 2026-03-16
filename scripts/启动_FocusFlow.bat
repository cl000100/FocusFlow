@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动 FocusFlow...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe launcher.pyw
) else (
    python launcher.pyw
)
pause
