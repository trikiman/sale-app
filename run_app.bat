@echo off
echo ===================================
echo  VkusVill Sale Monitor - Starting
echo ===================================

:: Start Telegram Bot (handles /sales, /check, cart buttons)
start "Telegram Bot" cmd /k "cd /d %~dp0 && python -u main.py"

:: Start Backend (FastAPI on port 8000)
start "Backend :8000" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --loop asyncio"

:: Start Scheduler (scrapers in PARALLEL every 5 min)
start "Scheduler" cmd /k "cd /d %~dp0 && python scheduler_service.py"

echo.
echo All services started:
echo   Telegram:  Bot is polling (check its window)
echo   Backend:   http://localhost:8000  (serves frontend too)
echo   Admin:     http://localhost:8000/admin
echo   Token:     (set ADMIN_TOKEN in .env)
echo.
echo NOTE: Frontend is served by Backend (production build).
echo       Run "cd miniapp ^&^& npm run build" after UI changes.
echo.
pause
