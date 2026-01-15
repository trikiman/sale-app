#!/bin/bash
set -euo pipefail

# Path to scraper - reliable discovery regardless of call location
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRAPER="$REPO_DIR/scrape_undetected.py"
LOG_FILE="$REPO_DIR/logs/cron.log"

# Wrapper script for cron
WRAPPER="$REPO_DIR/run_scraper.sh"

echo "Creating wrapper script at $WRAPPER..."

cat << EOF > "$WRAPPER"
#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd "$REPO_DIR"

# Ensure log directory exists
mkdir -p logs

# Run scraper with auto-allocated Xvfb display
# Using -a to avoid lock file contention
xvfb-run -a --server-args="-screen 0 1920x1080x24" /usr/bin/python3 "$SCRAPER" >> "$REPO_DIR/logs/cron.log" 2>&1
EOF

chmod +x "$WRAPPER"

echo "Adding to crontab..."
# Add to crontab (runs every 15 minutes)
# We use a temp file to avoid messing up crontab on partial failures
TMP_CRON=$(mktemp)
crontab -l 2>/dev/null > "$TMP_CRON" || true
# Remove existing entry for this specific wrapper to avoid duplicates if run multiple times
grep -v "$WRAPPER" "$TMP_CRON" > "$TMP_CRON.new" || true
echo "*/15 * * * * $WRAPPER" >> "$TMP_CRON.new"
crontab "$TMP_CRON.new"
rm "$TMP_CRON" "$TMP_CRON.new"

echo "✅ Cron job added: runs every 15 minutes"
echo "Logs will be in: $REPO_DIR/logs/cron.log"
