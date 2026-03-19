@echo off
echo ===================================
echo  VkusVill Sale Monitor - Starting
echo ===================================

:: Kill leftover processes from previous run
python "%~dp0kill_workspace.py"
echo Waiting 2 seconds...
timeout /t 2 /nobreak >nul

:: Start Chrome for scrapers FIRST (via PowerShell — Python can't launch Chrome)
:: Chrome will listen on port 19222 for CDP connections from scrapers.
echo Starting Chrome for scrapers...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_chrome.ps1"

:: Start Telegram Bot (handles /sales, /check, cart buttons)
start "Telegram Bot" python -u "%~dp0main.py"

:: Start Backend (FastAPI on port 8000)
start "Backend :8000" python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --loop asyncio

:: Start Scheduler (scrapers every 5 min)
start "Scheduler" python "%~dp0scheduler_service.py"

echo.
echo All services started:
echo   Chrome:    CDP on port 19222 (for scrapers)
echo   Telegram:  Bot is polling (check its window)
echo   Backend:   http://localhost:8000  (serves frontend too)
echo   Admin:     http://localhost:8000/admin
echo   Token:     (set ADMIN_TOKEN in .env)
echo.
echo NOTE: Frontend is served by Backend (production build).
echo       Run "cd miniapp ^&^& npm run build" after UI changes.
echo.
pause
