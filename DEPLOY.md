# Deployment Guide: VkusVill Scraper on AWS EC2

This guide details the steps to deploy the Python Selenium scraper (`scrape_prices.py`) to an AWS EC2 instance running Ubuntu 22.04.

## 1. Prerequisites

- **Instance Type**: `t3.medium` (recommended for stable Chrome execution).
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

To run the scraper manually with a virtual display:

```bash
xvfb-run -a --server-args="-screen 0 1920x1080x24" python3 scrape_prices.py
```

This command:
- Starts a virtual X server.
- Sets the screen resolution to 1920x1080 with 24-bit color.
- Executes the scraper within that environment.

## 5. Cron Setup

To automate the scraper execution, we will use the `setup_cron.sh` script. This script handles the scheduling and ensures the scraper runs within the Xvfb environment.

Example manual crontab entry (runs every 15 minutes to match setup_cron.sh):
```bash
# Run every 15 minutes
*/15 * * * * cd /home/ubuntu/saleapp && /usr/bin/xvfb-run -a --server-args="-screen 0 1920x1080x24" /usr/bin/python3 scrape_prices.py >> /home/ubuntu/saleapp/logs/cron.log 2>&1
```

Refer to `setup_cron.sh` for automated configuration.
