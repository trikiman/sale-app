@echo off
REM VkusVill Auto-Scraper for Windows
REM Run this with Task Scheduler every 5 minutes

cd /d "%~dp0"

echo [%date% %time%] Starting scrape... >> logs\scraper.log

REM Run scraper
python scrape_prices.py >> logs\scraper.log 2>&1

IF %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] Scrape SUCCESS >> logs\scraper.log
    
    REM Copy fresh data to miniapp
    copy /Y "data\proposals.json" "miniapp\public\data.json" >nul 2>&1
    
    REM Run notifier (optional)
    python backend\notifier.py --dry-run >> logs\scraper.log 2>&1
) ELSE (
    echo [%date% %time%] Scrape FAILED >> logs\scraper.log
)

echo [%date% %time%] Done >> logs\scraper.log
