# Deployment Guide: VkusVill Scraper on AWS EC2

This guide details the steps to deploy the Parallel VkusVill Scraper (`scrape_parallel.sh`) to an AWS EC2 instance running Ubuntu 22.04.

## 1. Prerequisites

- **Instance Type**: `t3.medium` or `t3.large` (recommended for running 3 Chrome instances in parallel).
- **Operating System**: Ubuntu 22.04 LTS.
- **Security Group**: Ensure SSH (port 22) access is enabled.

## 2. Initial Setup

Connect to your instance via SSH and run the following commands to install system dependencies:

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python, Pip, Xvfb, and other utilities
sudo apt install -y python3 python3-pip xvfb unzip wget gnupg

# Install Google Chrome Stable
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

# Verify installations
google-chrome --version
python3 --version
```

## 3. Project Setup

Clone the repository and install the Python dependencies:

```bash
# Clone the repository
git clone <your-repository-url>
cd saleapp
mkdir -p logs

# Install requirements
pip3 install -r requirements.txt
```

## 4. Headless Configuration (Xvfb)

Since `undetected-chromedriver` works best when it thinks it's running in a real display environment, we use `Xvfb` (X Virtual Framebuffer) to provide a virtual display.

To run the parallel scraper manually with a virtual display:

```bash
# Make script executable
chmod +x scrape_parallel.sh

# Run with Xvfb
xvfb-run -a --server-args="-screen 0 1920x1080x24" ./scrape_parallel.sh
```

This command:
- Starts a virtual X server.
- Sets the screen resolution to 1920x1080 with 24-bit color.
- Launches 3 parallel Chrome instances (Green, Red, Yellow).
- Merges the results into `data/proposals.json`.

## 5. Profile Synchronization (Optional)

If you need to log in (for Green prices), you can log in once to the shared profile and then sync it to the parallel profiles:

```bash
# 1. Run setup_login.py (requires X forwarding or desktop)
python3 setup_login.py

# 2. Sync the login session to all profiles
python3 sync_profiles.py
```

## 6. Cron Setup

To automate the scraper execution, we will use the `setup_cron.sh` script. This script handles the scheduling and ensures the scraper runs within the Xvfb environment.

Example manual crontab entry (runs every 15 minutes to match setup_cron.sh):
```bash
# Run every 15 minutes
*/15 * * * * cd /home/ubuntu/saleapp && /usr/bin/xvfb-run -a --server-args="-screen 0 1920x1080x24" /bin/bash scrape_parallel.sh >> /home/ubuntu/saleapp/logs/cron.log 2>&1
```

Refer to `setup_cron.sh` for automated configuration.
