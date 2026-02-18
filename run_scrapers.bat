@echo off
echo Starting SaleApp Scraper Service...
echo This service runs scrapers in parallel every 5 minutes.
title SaleApp Scraper Service

python scheduler_service.py

pause