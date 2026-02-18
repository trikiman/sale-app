@echo off
echo Starting ONE-TIME parallel scrape...
powershell -ExecutionPolicy Bypass -File scrape_parallel.ps1
pause
