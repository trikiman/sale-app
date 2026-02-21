# AWS EC2 Deployment & Verification Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a deployment verification guide and scripts for running the VkusVill scraper on AWS EC2 via Cron.

**Architecture:**
- The Python scraper (`scrape_prices.py`) runs in a persistent Chrome profile.
- A deployment checklist (`DEPLOY.md`) will guide the setup on a fresh EC2 instance.
- A verification script (`verify_deployment.sh`) will check dependencies, paths, and functionality.
- A setup script (`setup_cron.sh`) will configure the system cron job.

**Tech Stack:** Python 3, Selenium/Undetected Chromedriver, Xvfb (for headless display on server), Crontab, Bash.

---

### Task 1: Create Deployment Guide (DEPLOY.md)

**Files:**
- Create: `DEPLOY.md`

**Step 1: Write the content**

Create a comprehensive Markdown file with:
1.  **Prerequisites**: Instance type (t3.medium recommended for Chrome), OS (Ubuntu 22.04 LTS).
2.  **Initial Setup**: Commands to update apt, install Python 3, pip, Google Chrome, and Xvfb.
3.  **Project Setup**: Cloning repo, installing requirements.
4.  **Headless Configuration**: Instructions for setting up Xvfb since `undetected_chromedriver` often needs a display context even in headless mode on Linux servers.
5.  **Cron Setup**: How to schedule the job.

**Step 2: Commit**

```bash
git add DEPLOY.md
git commit -m "docs: add deployment guide for AWS EC2"
```

### Task 2: Create Verification Script

**Files:**
- Create: `verify_deployment.sh`

**Step 1: Write the verification script**

This script will run on the EC2 instance to ensure it's ready.

```bash
#!/bin/bash
set -e

echo "=== Verifying Deployment Environment ==="

# 1. Check Python
python3 --version || { echo "❌ Python 3 not found"; exit 1; }
echo "✅ Python 3 found"

# 2. Check Chrome
google-chrome --version || { echo "❌ Google Chrome not found"; exit 1; }
echo "✅ Google Chrome found"

# 3. Check Dependencies
pip3 install -r requirements.txt
echo "✅ Dependencies verified"

# 4. Check Directories
[ -d "data" ] || mkdir data
[ -d "miniapp/public" ] || mkdir -p miniapp/public
echo "✅ Directories ready"

# 5. Dry Run Scraper (if possible, or just import check)
python3 -c "import undetected_chromedriver; print('✅ undetected_chromedriver importable')"

echo "=== Verification Complete ==="
```

**Step 2: Make executable**

```bash
chmod +x verify_deployment.sh
```

**Step 3: Commit**

```bash
git add verify_deployment.sh
git commit -m "ops: add deployment verification script"
```

### Task 3: Create Cron Setup Script

**Files:**
- Create: `setup_cron.sh`

**Step 1: Write the cron setup script**

Automates the addition of the cron job.

```bash
#!/bin/bash

# Path to scraper
REPO_DIR=$(pwd)
SCRAPER="$REPO_DIR/scrape_prices.py"
LOG_FILE="$REPO_DIR/cron.log"

# Wrapper script for cron (handles env vars and Xvfb)
WRAPPER="$REPO_DIR/run_scraper.sh"

cat << EOF > "$WRAPPER"
#!/bin/bash
export DISPLAY=:99
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd "$REPO_DIR"
/usr/bin/python3 "$SCRAPER" >> "$LOG_FILE" 2>&1
EOF

chmod +x "$WRAPPER"

# Add to crontab (runs every 15 minutes)
(crontab -l 2>/dev/null; echo "*/15 * * * * $WRAPPER") | crontab -

echo "✅ Cron job added: runs every 15 minutes"
echo "Logs will be in: $LOG_FILE"
```

**Step 2: Make executable**

```bash
chmod +x setup_cron.sh
```

**Step 3: Commit**

```bash
git add setup_cron.sh
git commit -m "ops: add cron setup automation"
```
