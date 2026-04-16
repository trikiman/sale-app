@echo off
REM Setup scheduled health check for VkusVill Sale Monitor
REM Run this as Administrator to create the scheduled task

echo Creating scheduled task for health monitoring...

schtasks /create /tn "VkusVill Health Check" /tr "python.exe e:\Projects\saleapp\health_check.py" /sc hourly /f

if %errorlevel% equ 0 (
    echo SUCCESS: Scheduled task created!
    echo Health check will run every hour automatically.
    echo.
    echo To verify: schtasks /query /tn "VkusVill Health Check"
    echo To run now: schtasks /run /tn "VkusVill Health Check"
    echo To delete: schtasks /delete /tn "VkusVill Health Check" /f
) else (
    echo ERROR: Failed to create scheduled task. Run as Administrator.
)

pause
