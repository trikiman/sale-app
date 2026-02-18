@echo off
echo Starting SaleApp Application...

:: Start Backend Server
start "SaleApp Backend" cmd /k "python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

:: Start Frontend Server
cd miniapp
start "SaleApp Frontend" cmd /k "npm run dev"

echo Application services started.
pause