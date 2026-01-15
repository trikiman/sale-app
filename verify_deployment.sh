#!/bin/bash
set -euo pipefail

echo "=== Verifying Deployment Environment ==="

# 1. Check Python
python3 --version || { echo "❌ Python 3 not found"; exit 1; }
echo "✅ Python 3 found"

# 2. Check Chrome
google-chrome --version || { echo "❌ Google Chrome not found"; exit 1; }
echo "✅ Google Chrome found"

# 3. Check Dependencies
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found"
    exit 1
fi
python3 -m pip install -r requirements.txt
echo "✅ Dependencies verified"

# 4. Check Directories
mkdir -p data
mkdir -p miniapp/public
echo "✅ Directories ready"

# 5. Dry Run Scraper (if possible, or just import check)
python3 -c "import undetected_chromedriver; print('✅ undetected_chromedriver importable')"

echo "=== Verification Complete ==="
