#!/bin/bash
cd /home/ubuntu/saleapp
BEFORE=$(git rev-parse HEAD)
git pull --ff-only origin main 2>/dev/null
AFTER=$(git rev-parse HEAD)
if [ "$BEFORE" != "$AFTER" ]; then
    echo "$(date): Updated from $BEFORE to $AFTER" >> /home/ubuntu/saleapp/logs/auto_pull.log
    CHANGED=$(git diff --name-only "$BEFORE" "$AFTER")
    if echo "$CHANGED" | grep -qE 'backend/|config.py|bot/'; then
        sudo systemctl restart saleapp-backend
        echo "$(date): Restarted saleapp-backend" >> /home/ubuntu/saleapp/logs/auto_pull.log
    fi
fi
