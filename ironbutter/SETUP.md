# Setup Guide

Complete setup instructions for the OpenAlgo 9:20 Iron Butterfly Trading System.

## Prerequisites

- Zerodha trading account with F&O enabled
- ~₹55,000 available margin
- Kite Connect API subscription (₹500/month)
- Oracle Cloud account (free)

## Step 1: Oracle Cloud VM

### Create Account
1. Go to [cloud.oracle.com/free](https://cloud.oracle.com/free)
2. Sign up with email, phone verification
3. Add credit card (verification only, not charged)
4. **Select Home Region: India South (Hyderabad) or India West (Mumbai)**

### Create VM
1. Go to Compute → Instances → Create Instance
2. Settings:
   - Image: **Ubuntu 22.04**
   - Shape: **VM.Standard.E2.1.Micro** (Always Free)
3. Networking:
   - Create VCN with Internet Gateway (use VCN Wizard)
   - Ensure public subnet with public IP
   - Security list: Allow TCP port 22 (SSH)
4. SSH Keys: Generate and **download private key**
5. Note the **Public IP address**

### Your VM Details
```
IP: <your-vm-public-ip>
User: ubuntu
SSH Key: ~/path/to/your-ssh-key.key
```

## Step 2: Kite Connect API

### Get API Credentials
1. Go to [kite.trade](https://kite.trade)
2. Create app (Connect type - ₹500/month)
3. Note: `API Key` and `API Secret`
4. Set Redirect URL: `http://127.0.0.1:5000/`

### Get TOTP Secret
1. Go to Zerodha Console → My Profile → Security
2. Enable External 2FA TOTP
3. Click "Can't scan?" to see the secret key
4. Copy the secret (e.g., `JBSWY3DPEHPK3PXP`)

## Step 3: VM Setup

### SSH into VM
```bash
chmod 400 ~/path/to/your-ssh-key.key
ssh -i ~/path/to/your-ssh-key.key ubuntu@<your-vm-public-ip>
```

### Install Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Python packages
sudo apt install -y python3-pip
pip3 install kiteconnect pyotp playwright python-dotenv requests

# Install Playwright browser
export PATH=$PATH:/home/ubuntu/.local/bin
playwright install chromium

# Install browser dependencies
sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
  libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libasound2
```

### Create Directories
```bash
mkdir -p /home/ubuntu/scripts/trade_history
sudo mkdir -p /var/log/openalgo
sudo chown ubuntu:ubuntu /var/log/openalgo
```

## Step 4: Deploy Scripts

### Copy from Local Machine
```bash
# From your Mac
scp -i ~/path/to/your-ssh-key.key -r ./scripts ubuntu@<your-vm-public-ip>:/home/ubuntu/
```

### Create .env File
```bash
# On VM
cp /home/ubuntu/scripts/env.sample /home/ubuntu/scripts/.env
nano /home/ubuntu/scripts/.env
```

Fill in your credentials:
```
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_USER_ID=your_user_id
KITE_PASSWORD=your_password
TOTP_SECRET=your_totp_secret
TRADING_SYMBOL=NIFTY
QUANTITY=50
STOP_LOSS_PERCENT=30
EXIT_TIME=15:15
HEDGE_DISTANCE=150
```

### Set Permissions
```bash
chmod 600 /home/ubuntu/scripts/.env
chmod +x /home/ubuntu/scripts/*.py
```

## Step 5: Setup Cron Jobs

```bash
crontab -e
```

Add:
```cron
# 8:30 AM IST = 3:00 AM UTC - Auto login
0 3 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/auto_login.py >> /var/log/openalgo/auto_login.log 2>&1

# 9:20 AM IST = 3:50 AM UTC - Execute strategy
50 3 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/straddle_920.py >> /var/log/openalgo/straddle.log 2>&1

# Monitor every 1 minute
*/1 4-10 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/straddle_920.py monitor >> /var/log/openalgo/straddle.log 2>&1
```

## Step 6: Test

### Test Auto-Login
```bash
python3 /home/ubuntu/scripts/auto_login.py
```

Expected output:
```
AUTO-LOGIN COMPLETED SUCCESSFULLY
```

### Test Strategy (Only During Market Hours)
```bash
python3 /home/ubuntu/scripts/straddle_920.py
```

## Verification Checklist

- [ ] VM accessible via SSH
- [ ] Docker installed
- [ ] Python dependencies installed
- [ ] .env file configured with credentials
- [ ] Auto-login script works
- [ ] Cron jobs installed
- [ ] Sufficient margin in Zerodha account (~₹55,000)

## Maintenance

### Check Logs Daily
```bash
tail -100 /var/log/openalgo/straddle.log
tail -100 /var/log/openalgo/auto_login.log
```

### Verify Cron Running
```bash
crontab -l
```

### Check Current Position
```bash
cat /home/ubuntu/scripts/current_position.json
```

### View Trade History
```bash
ls -la /home/ubuntu/scripts/trade_history/
cat /home/ubuntu/scripts/trade_history/YYYY-MM-DD_iron_butterfly.json
```

