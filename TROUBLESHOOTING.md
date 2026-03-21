# Troubleshooting & Operations Guide

## Trading Controls

### Method 1: Kill Switch (Instant Stop/Resume)

**Stop all trading immediately:**
```bash
# If on VM directly
touch /home/ubuntu/scripts/STOP_TRADING

# If from your Mac
ssh -i ~/path/to/your-ssh-key.key ubuntu@<your-vm-ip> "touch /home/ubuntu/scripts/STOP_TRADING"
```

**Resume trading:**
```bash
# If on VM directly
rm /home/ubuntu/scripts/STOP_TRADING

# If from your Mac
ssh -i ~/path/to/your-ssh-key.key ubuntu@<your-vm-ip> "rm /home/ubuntu/scripts/STOP_TRADING"
```

### Method 2: Skip Specific Dates

Create/edit a file with dates to skip (one per line, YYYY-MM-DD format):

```bash
# Add a single date
echo "2026-02-01" >> /home/ubuntu/scripts/skip_dates.txt

# Add multiple dates
cat > /home/ubuntu/scripts/skip_dates.txt << EOF
2026-02-01
2026-02-28
2026-03-15
EOF

# View skip dates
cat /home/ubuntu/scripts/skip_dates.txt

# Clear all skip dates
rm /home/ubuntu/scripts/skip_dates.txt
```

**Recommended dates to skip:**
- Budget Day (usually Feb 1)
- RBI Policy Days (bi-monthly)
- Election Results Days
- Major global events
- F&O Expiry days (Thursdays) - optional

### Method 3: Disable Cron Jobs

```bash
# Edit crontab
crontab -e

# Add # before lines to disable:
#50 3 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/straddle_920.py ...
#*/1 4-10 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/straddle_920.py monitor ...

# Or remove all crons entirely
crontab -r
```

### Check Trading Status

```bash
# Quick status check
if [ -f /home/ubuntu/scripts/STOP_TRADING ]; then 
    echo '🔴 TRADING STOPPED'
else 
    echo '🟢 TRADING ACTIVE'
fi

# Check skip dates
cat /home/ubuntu/scripts/skip_dates.txt 2>/dev/null || echo "No skip dates configured"

# Check if cron is active
crontab -l | grep -v "^#" | grep straddle && echo "Cron ACTIVE" || echo "Cron DISABLED"
```

---

## Common Issues and Solutions

---

## Auto-Login Issues

### Problem: "Failed to obtain request_token"

**Symptoms**:
```
ERROR - Failed to obtain request_token. Exiting.
```

**Solutions**:

1. **Check credentials in .env**:
   ```bash
   cat /home/ubuntu/scripts/.env | grep KITE
   ```

2. **Verify TOTP secret is correct**:
   - Test manually: Go to kite.zerodha.com
   - Enter your credentials
   - Compare TOTP code from your authenticator app

3. **Check screenshot for clues**:
   ```bash
   ls -la /var/log/openalgo/*.png
   # Copy to local machine to view
   scp -i ~/path/to/your-ssh-key.key ubuntu@<your-vm-ip>:/var/log/openalgo/*.png ~/Downloads/
   ```

4. **Zerodha may have changed their UI**:
   - Check if login page structure changed
   - May need to update Playwright selectors in script

### Problem: "TOTP input not found"

**Solution**: Update the TOTP selector in `auto_login.py`:
```python
# Current selectors - may need updating
totp_selectors = [
    'input[type="number"]',
    'input[type="tel"]',
    'input[inputmode="numeric"]',
    # Add new selectors if Zerodha changed UI
]
```

---

## Order Execution Issues

### Problem: "Insufficient margin"

**Symptoms**:
```
kiteconnect.exceptions.InputException: Insufficient margin
```

**Solutions**:

1. **Check available margin in Kite**:
   - Login to kite.zerodha.com
   - Go to Funds
   - Ensure ~₹55,000 available

2. **Reduce position size**:
   ```bash
   nano /home/ubuntu/scripts/.env
   # Change QUANTITY=50 to QUANTITY=25 (half lot - not recommended)
   ```

3. **Increase hedge distance** (reduces margin but also reduces profit):
   ```bash
   # In .env
   HEDGE_DISTANCE=200  # instead of 150
   ```

### Problem: "Order rejected"

**Possible causes**:
- Market closed (weekends/holidays)
- Invalid symbol (expiry changed)
- Circuit limits hit
- Account restrictions

**Debug**:
```bash
# Check the full error in logs
grep -i "error\|reject" /var/log/openalgo/straddle.log | tail -20
```

---

## Monitoring Issues

### Problem: Position not being monitored

**Check cron is running**:
```bash
crontab -l
# Should show the monitoring cron entry

# Check cron logs
grep CRON /var/log/syslog | tail -20
```

**Check position file exists**:
```bash
cat /home/ubuntu/scripts/current_position.json
```

### Problem: Stop-loss not triggering

**Check the calculation**:
```bash
# View current position
cat /home/ubuntu/scripts/current_position.json

# Check logs for monitoring output
tail -50 /var/log/openalgo/straddle.log
```

---

## VM/Infrastructure Issues

### Problem: Cannot SSH into VM

**Solutions**:

1. **Check if VM is running**:
   - Oracle Cloud Console → Compute → Instances
   - Should show "Running"

2. **Check security list**:
   - VCN → Security Lists
   - Ensure ingress rule for TCP port 22 from 0.0.0.0/0

3. **Check route table**:
   - VCN → Route Tables
   - Ensure route to Internet Gateway (0.0.0.0/0 → IGW)

4. **Verify SSH key**:
   ```bash
   chmod 400 ~/path/to/your-ssh-key.key
   ssh -v -i ~/path/to/your-ssh-key.key ubuntu@<your-vm-ip>
   ```

### Problem: VM out of memory

**Check memory**:
```bash
free -h
```

**Solution**: The free tier VM has 1GB RAM. If running out:
- Restart the VM from Oracle Console
- Reduce running processes

---

## Kite API Issues

### Problem: "Access token expired"

**Symptoms**:
```
kiteconnect.exceptions.TokenException: Token is invalid or has expired
```

**Solution**: Run auto-login manually:
```bash
python3 /home/ubuntu/scripts/auto_login.py
```

### Problem: Rate limiting

**Symptoms**:
```
kiteconnect.exceptions.NetworkException: Too many requests
```

**Solution**: The script already has delays between orders. If persistent:
- Increase sleep times in script
- Contact Kite support

---

## Log Locations

| Log | Location | Purpose |
|-----|----------|---------|
| Auto-login | `/var/log/openalgo/auto_login.log` | Login attempts |
| Strategy | `/var/log/openalgo/straddle.log` | Trades & monitoring |
| System | `/var/log/syslog` | Cron execution |
| Screenshots | `/var/log/openalgo/*.png` | Login failures |

## Useful Commands

```bash
# View last 100 lines of strategy log
tail -100 /var/log/openalgo/straddle.log

# Watch logs in real-time
tail -f /var/log/openalgo/straddle.log

# Search for errors
grep -i error /var/log/openalgo/*.log

# Check disk space
df -h

# Check running processes
ps aux | grep python

# Restart cron service
sudo systemctl restart cron

# Test script manually
python3 /home/ubuntu/scripts/auto_login.py
python3 /home/ubuntu/scripts/straddle_920.py
```

## Emergency: Stop All Trading

```bash
# Remove cron jobs
crontab -r

# Or comment them out
crontab -e
# Add # before each line

# Delete current position (won't auto-exit)
rm /home/ubuntu/scripts/current_position.json
```

**Important**: If you delete position file, manually close positions in Kite!

## Getting Help

1. **Check this documentation first**
2. **Review logs for specific errors**
3. **Test components individually**:
   - Auto-login: `python3 auto_login.py`
   - Strategy: `python3 straddle_920.py` (only during market hours)
4. **For Kite API issues**: [Kite Connect Documentation](https://kite.trade/docs/connect/)

