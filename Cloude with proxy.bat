@echo off
title Antigravity Launcher

:: Configuration
set "PROXY_DIR=E:\Projects\cloude code\antigravity-claude-proxy"
set "PORT=8080"

echo ===================================================
echo   Starting Antigravity System
echo ===================================================

:: 1. Start Proxy (Visible CMD Window)
echo.
echo [1/3] Starting Proxy Server...
start "Antigravity Proxy" cmd /k "cd /d "%PROXY_DIR%" && set PORT=%PORT% && npm start"

:: 2. Wait for server to be ready
echo       Waiting 4 seconds...
timeout /t 4 /nobreak >nul

:: 3. Open Web UI
echo.
echo [2/3] Opening Web UI...
start http://localhost:%PORT%

:: 4. Start Claude (New PowerShell Window)
echo.
echo [3/3] Launching Claude in PowerShell...
start powershell -NoExit -Command "$env:ANTHROPIC_BASE_URL='http://localhost:%PORT%'; $env:ANTHROPIC_AUTH_TOKEN='test'; & 'C:\Users\rust-\AppData\Roaming\npm\claude.cmd' --dangerously-skip-permissions"

echo.
echo Done! You can close this launcher window.
timeout /t 3 >nul
exit
