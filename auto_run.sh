#!/bin/bash
# ==============================================
# VkusVill Auto-Scraper for EC2
# Runs every 5 minutes via cron
# ==============================================
#
# SETUP ON EC2:
# 1. Make executable:    chmod +x auto_run.sh
# 2. Edit crontab:       crontab -e
# 3. Add this line:      */5 * * * * /home/ubuntu/saleapp/auto_run.sh
# 4. Save and exit
#
# ==============================================

# Go to project directory
cd /home/ubuntu/saleapp || exit 1

# Activate virtual environment
source venv/bin/activate

# Create logs dir if needed
mkdir -p logs

# Log file with date
LOG="logs/scrape_$(date +%Y%m%d).log"

echo "" >> "$LOG"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG"

# Run scraper
echo "Starting scraper..." >> "$LOG"
timeout 300 python scrape_prices.py >> "$LOG" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Scrape SUCCESS" >> "$LOG"
    
    # Copy data to miniapp public folder
    cp data/proposals.json miniapp/public/data.json 2>/dev/null
    
    # Run notifier if ADMIN_ID is set
    if [ -n "$TELEGRAM_ADMIN_ID" ]; then
        python backend/notifier.py --admin "$TELEGRAM_ADMIN_ID" >> "$LOG" 2>&1
    fi
else
    echo "❌ Scrape FAILED (exit code $EXIT_CODE)" >> "$LOG"
fi

# Cleanup old logs (keep 7 days)
find logs -name "scrape_*.log" -mtime +7 -delete 2>/dev/null

echo "Done" >> "$LOG"
