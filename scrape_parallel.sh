#!/bin/bash

# VkusVill Parallel Scraper (Linux/Bash)
# Runs Green, Red, and Yellow scrapers in parallel, then merges results.

# Ensure we are in the script's directory
cd "$(dirname "$0")"
mkdir -p logs

echo "============================================================"
echo "VkusVill PARALLEL Scraper"
echo "Time: $(date)"
echo "============================================================"

echo "🚀 Launching 3 parallel scrapers..."

# Run scrapers in background
# We use wait to ensure they all finish before merging

python3 scrape_green.py > logs/green.log 2>&1 &
PID_GREEN=$!
echo "  [Green] Started (PID: $PID_GREEN)"

python3 scrape_red.py > logs/red.log 2>&1 &
PID_RED=$!
echo "  [Red] Started (PID: $PID_RED)"

python3 scrape_yellow.py > logs/yellow.log 2>&1 &
PID_YELLOW=$!
echo "  [Yellow] Started (PID: $PID_YELLOW)"

# Wait for all processes to complete
wait $PID_GREEN
STATUS_GREEN=$?

wait $PID_RED
STATUS_RED=$?

wait $PID_YELLOW
STATUS_YELLOW=$?

echo "⏳ All scrapers completed."
echo "  Green exit code: $STATUS_GREEN"
echo "  Red exit code: $STATUS_RED"
echo "  Yellow exit code: $STATUS_YELLOW"

# Merge results
echo ""
echo "🔀 Merging all products..."
python3 scrape_merge.py

echo ""
echo "✅ Done!"
