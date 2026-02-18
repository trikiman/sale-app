@echo off
echo ===================================
echo  VkusVill Sale Monitor - Starting
echo ===================================

:: Start Backend (FastAPI on port 8000)
start "Backend :8000" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Start Scheduler (scrapers every 5 min)
start "Scheduler" cmd /k "cd /d %~dp0 && python scheduler.py"

:: Start Frontend (React/Vite on port 5173)
start "Frontend :5173" cmd /k "cd /d %~dp0\miniapp && npm run dev"

echo.
echo All services started:
echo   Backend:   http://localhost:8000
echo   Admin:     http://localhost:8000/admin
echo   Frontend:  http://localhost:5173
echo   Token:     vv-admin-2026
echo.
pause
