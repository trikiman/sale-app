#!/bin/bash
# VkusVill Scraper - Oracle Cloud VPS Setup Script
# Run this after connecting to your VPS via SSH

echo "=========================================="
echo "VkusVill Scraper - VPS Setup"
echo "=========================================="

# Update system
echo "Updating system..."
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
echo "Installing Python..."
sudo apt install -y python3 python3-pip python3-venv

# Install Chrome/Chromium for ARM
echo "Installing Chromium..."
sudo apt install -y chromium-browser chromium-chromedriver

# Install X virtual framebuffer (for headless Chrome)
echo "Installing Xvfb..."
sudo apt install -y xvfb

# Create virtual environment
echo "Creating Python environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "Installing Python packages..."
pip install undetected-chromedriver selenium schedule requests

# Create data directory
mkdir -p data
mkdir -p miniapp/public

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Upload your scraper files"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python scrape_vps.py (to login once)"
echo "4. Set up cron job for auto-scraping"
