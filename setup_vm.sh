#!/bin/bash
#
# OpenAlgo VM Setup Script
# ========================
# Run this script on your Oracle Cloud VM to set up everything.
#
# Usage:
#   chmod +x setup_vm.sh
#   ./setup_vm.sh
#

set -e  # Exit on error

echo "=========================================="
echo "OpenAlgo Trading System Setup"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create directories
echo -e "${GREEN}Creating directories...${NC}"
mkdir -p /home/ubuntu/scripts
mkdir -p /home/ubuntu/scripts/trade_history
sudo mkdir -p /var/log/openalgo
sudo chown ubuntu:ubuntu /var/log/openalgo

# Install Python packages
echo -e "${GREEN}Installing Python packages...${NC}"
pip3 install --user kiteconnect pyotp playwright python-dotenv requests

# Install Playwright browsers
echo -e "${GREEN}Installing Playwright browsers...${NC}"
playwright install chromium
playwright install-deps || sudo playwright install-deps

# Copy scripts to the right location
echo -e "${GREEN}Setting up scripts...${NC}"
if [ -f "/home/ubuntu/oa/scripts/auto_login.py" ]; then
    cp /home/ubuntu/oa/scripts/auto_login.py /home/ubuntu/scripts/
    cp /home/ubuntu/oa/scripts/straddle_920.py /home/ubuntu/scripts/
fi

chmod +x /home/ubuntu/scripts/*.py 2>/dev/null || true

# Setup cron jobs
echo -e "${GREEN}Setting up cron jobs...${NC}"
(crontab -l 2>/dev/null | grep -v "auto_login.py\|straddle_920.py"; cat << 'EOF'
# OpenAlgo Trading Cron Jobs
# ==========================

# 8:30 AM IST = 3:00 AM UTC - Auto login to refresh token
0 3 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/auto_login.py >> /var/log/openalgo/auto_login.log 2>&1

# 9:20 AM IST = 3:50 AM UTC - Execute 9:20 straddle
50 3 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/straddle_920.py >> /var/log/openalgo/straddle.log 2>&1

# Monitor straddle every 5 minutes from 9:30 AM to 3:30 PM IST (4:00 AM to 10:00 AM UTC)
*/5 4-10 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/straddle_920.py monitor >> /var/log/openalgo/straddle.log 2>&1
EOF
) | crontab -

echo -e "${GREEN}Cron jobs installed:${NC}"
crontab -l

# Start OpenAlgo (if docker-compose is available)
echo -e "${GREEN}Starting OpenAlgo...${NC}"
if [ -f "/home/ubuntu/openalgo/docker-compose.yaml" ]; then
    cd /home/ubuntu/openalgo
    docker-compose up -d
    echo "OpenAlgo container started."
else
    echo -e "${YELLOW}OpenAlgo docker-compose not found. Skipping container start.${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit /home/ubuntu/scripts/.env with your credentials"
echo "2. Test auto-login: python3 /home/ubuntu/scripts/auto_login.py"
echo "3. Check logs: tail -f /var/log/openalgo/auto_login.log"
echo ""

