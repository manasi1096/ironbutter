# 9:20 AM Credit Spread Strategy

## Overview

An automated options trading system that executes a **single credit spread** on NIFTY at 9:20 AM IST daily. The spread direction is auto-selected based on market gap at open.

**Key Features:**
- Fully automated (no manual intervention required)
- Adapts to market conditions ("fade the gap" logic)
- Capped maximum loss due to hedge
- Runs on Oracle Cloud VM (free tier)
- Telegram notifications for all events

---

## Strategy Details

### What is a Credit Spread?

A credit spread involves:
1. **Selling** an ATM (at-the-money) option - receive premium
2. **Buying** an OTM (out-of-the-money) option - pay premium (hedge)

**Net result:** You receive a credit (premium difference) upfront.

| Spread Type | Legs | Profits When |
|-------------|------|--------------|
| **Put Credit Spread** | Sell ATM PE + Buy OTM PE | Market stays flat or goes UP |
| **Call Credit Spread** | Sell ATM CE + Buy OTM CE | Market stays flat or goes DOWN |

### Why 9:20 AM?

- Market opens at 9:15 AM IST
- First 5 minutes have high volatility and wide spreads
- By 9:20 AM, initial volatility settles, better fills
- Captures overnight gap reaction

---

## Auto-Selection Logic

At 9:20 AM, the system checks the **gap** between current price and previous day's close:

```
Gap = Current Price - Previous Close

If Gap > +50 points:  → PUT Credit Spread (expect pullback)
If Gap < -50 points:  → CALL Credit Spread (expect bounce)  
If Gap within ±50:    → PUT Credit Spread (default)
```

### Rationale ("Fade the Gap")

- Large gaps often **mean-revert** during the day
- Gap UP → Market overextended, likely to pull back → Sell puts
- Gap DOWN → Market oversold, likely to bounce → Sell calls
- Flat open → Slight bullish bias historically → Sell puts

---

## Entry Details

### Timing
- **Entry:** 9:20 AM IST (3:50 AM UTC)
- **Exit:** 3:15 PM IST (9:45 AM UTC) or stop-loss

### Order Sequence (Critical for Margin)
1. **Buy OTM option first** (hedge) - uses cash for premium
2. **Sell ATM option second** - now recognized as spread, lower margin

This sequence is crucial - selling naked first would require ~₹1.9L margin per leg.

### Strike Selection
- **ATM Strike:** Rounded to nearest 50 (e.g., NIFTY at 24807 → ATM = 24800)
- **OTM Strike:** ATM ± 150 points (hedge distance)
  - Put spread: OTM = ATM - 150
  - Call spread: OTM = ATM + 150

### Quantity
- **1 lot of NIFTY = 65 units** (as of 2025)

---

## Exit Rules

### Time-Based Exit
- Position auto-closes at **3:15 PM IST**
- Avoids last-hour volatility and expiry-day gamma risk

### Stop-Loss Exit
- Triggers at **50% of maximum loss**
- Example: If max loss = ₹6,000, stop-loss triggers at ₹3,000 loss

### Stop-Loss Calculation
```python
Max Loss = (Hedge Distance - Spread Credit) × Quantity
Stop Loss Threshold = Max Loss × 50%

# Example:
Hedge Distance = 150 points
Spread Credit = 60 points
Max Loss per share = 150 - 60 = 90 points
Max Loss Total = 90 × 65 = ₹5,850
Stop Loss = ₹2,925 loss
```

---

## Risk Management

### Capped Maximum Loss
The OTM hedge **caps** the maximum loss regardless of how far the market moves.

| Scenario | Without Hedge | With Hedge |
|----------|---------------|------------|
| Market crashes 500 pts | Unlimited loss | Max ₹5,850 |
| Market rallies 500 pts | Unlimited loss | Max ₹5,850 |

### Position Sizing
- **1 lot only** (65 units)
- Never scales up or adds to position
- Single spread per day

### Capital Requirement
| Component | Amount |
|-----------|--------|
| OTM Hedge Premium | ~₹7,000 - 10,000 |
| Spread Margin | ~₹25,000 - 35,000 |
| Buffer | ~₹10,000 |
| **Minimum Required** | **~₹50,000** |
| **Recommended** | **₹55,000 - 60,000** |

---

## Profit/Loss Expectations

### Typical Trade
| Metric | Value |
|--------|-------|
| Credit Received | ₹3,500 - 4,500 |
| Max Loss (capped) | ₹5,500 - 6,500 |
| Stop Loss | ~₹3,000 |
| Risk:Reward | ~1.5:1 |

### Profit Scenarios
| Market Behavior | Expected P&L |
|-----------------|--------------|
| Stays within ±100 pts of entry | +₹2,000 to +₹4,000 |
| Moves against but within hedge | -₹500 to +₹1,500 |
| Breaches hedge strike | -₹3,000 to -₹6,000 |

### Win Rate Expectation
- Theoretical: 60-70% (credit spreads have higher win rate but lower reward)
- Actual results will vary based on market conditions

---

## Infrastructure

### Oracle Cloud VM
- **Location:** Mumbai region (low latency to NSE)
- **Specs:** Always Free tier (1 GB RAM, 1 OCPU)
- **OS:** Ubuntu 22.04
- **IP:** `<your-vm-ip>`

### Scheduled Jobs (Cron - UTC)
| Time (UTC) | Time (IST) | Job |
|------------|------------|-----|
| 3:00 AM | 8:30 AM | Auto-login (refresh access token) |
| 3:50 AM | 9:20 AM | Execute strategy |
| 4:00-10:00 AM | 9:30 AM-3:30 PM | Monitor every minute |
| 10:05 AM | 3:35 PM | Send daily summary |

### Files on VM
```
/home/ubuntu/scripts/
├── .env                    # Credentials (API keys, tokens)
├── straddle_920.py         # Main strategy script
├── auto_login.py           # Daily login automation
├── telegram_notifier.py    # Notification functions
├── daily_summary.py        # EOD report script
├── current_position.json   # Active position (if any)
├── skip_dates.txt          # Dates to skip trading
├── STOP_TRADING            # Kill switch file (create to stop)
└── trade_history/          # Completed trades
```

---

## Controls

### Skip Trading on Specific Dates
Add dates to `/home/ubuntu/scripts/skip_dates.txt`:
```
2026-02-01
2026-02-28
2026-03-15
```

### Emergency Stop (Kill Switch)
Create file to stop all trading:
```bash
ssh ubuntu@<your-vm-ip> "touch /home/ubuntu/scripts/STOP_TRADING"
```

Remove to resume:
```bash
ssh ubuntu@<your-vm-ip> "rm /home/ubuntu/scripts/STOP_TRADING"
```

### Manual Position Close
If needed, log into Zerodha Kite web/app and close positions manually.

---

## Telegram Notifications

You receive notifications for:
- ✅ Trade entry (with gap direction, strikes, credit)
- ✅ Trade exit (with P&L, exit reason)
- ✅ Daily EOD summary (opening balance, P&L breakdown)
- ❌ Errors and failures
- ⏸️ Skipped trading days

---

## Caveats & Limitations

### 1. Margin Requirements Can Vary
Zerodha's SPAN margin changes based on volatility. During high-VIX periods, margin requirements increase. The strategy may fail to execute if margin spikes.

### 2. Slippage on Market Orders
All orders are market orders for guaranteed fills. In volatile conditions, fills may be worse than quoted prices.

### 3. Single Spread Only
Due to capital constraints (~₹55K), we trade only ONE spread (not the full Iron Butterfly). This means:
- Half the credit vs Iron Butterfly
- Directional bias (not fully neutral)
- Adapts via gap logic but not hedged both ways

### 4. Expiry Day Risk
On weekly expiry (Thursday), gamma risk is high. Consider adding Thursday to skip_dates if concerned.

### 5. Gap Threshold is Fixed
The ±50 point threshold for gap detection is hardcoded. May need adjustment for different volatility regimes.

### 6. No Adjustment Logic
Once position is opened, there's no adjustment (rolling, adding hedge, etc.). It either hits stop-loss, time-exit, or max loss.

### 7. Broker API Dependency
Relies on Zerodha Kite Connect API. Any API issues, rate limits, or maintenance windows can affect execution.

### 8. Access Token Expires Daily
Kite access tokens expire at midnight. Auto-login runs at 8:30 AM to refresh. If login fails, trading fails for the day.

### 9. API Transient Failures
Kite API can have momentary outages. The system now has **retry logic** (3 attempts with 5-10 second delays) to handle transient failures automatically.

---

## Performance Tracking

### Trade History
All completed trades are saved to:
```
/home/ubuntu/scripts/trade_history/YYYY-MM-DD_credit_spread.json
```

### Key Metrics to Track
- Win rate (% of profitable days)
- Average win vs average loss
- Maximum drawdown
- Sharpe ratio (if tracking daily returns)

### Viewing Recent Trades
```bash
ssh ubuntu@<your-vm-ip> "ls -la /home/ubuntu/scripts/trade_history/"
ssh ubuntu@<your-vm-ip> "cat /home/ubuntu/scripts/trade_history/YYYY-MM-DD_credit_spread.json"
```

---

## Quick Reference

### SSH Access
```bash
ssh -i ~/path/to/your-ssh-key.key ubuntu@<your-vm-ip>
```

### Check Current Status
```bash
# View logs
tail -50 /var/log/openalgo/straddle.log

# Check position
cat /home/ubuntu/scripts/current_position.json

# Check account balance
cd /home/ubuntu/scripts && python3 -c "
from dotenv import load_dotenv; load_dotenv()
import os; from kiteconnect import KiteConnect
k = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
k.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))
m = k.margins()
print(f'Balance: {m[\"equity\"][\"available\"][\"live_balance\"]:,.0f}')
"
```

### Update Skip Dates
```bash
echo "2026-03-20" >> /home/ubuntu/scripts/skip_dates.txt
```

---

## Changelog

| Version | Change |
|---------|--------|
| 1.0 | Initial setup with Iron Butterfly |
| 1.1 | Fixed order sequence (buy hedge first) |
| 1.2 | Switched to single spread (capital constraints) |
| 1.3 | Added auto-selection based on gap direction |
| 1.4 | Fixed timezone issue (UTC vs IST on VM) |
| 1.5 | Added retry logic for transient API failures |

---

## Summary

| Aspect | Detail |
|--------|--------|
| **Strategy** | Single Credit Spread (Put or Call) |
| **Entry** | 9:20 AM IST daily |
| **Exit** | 3:15 PM IST or 50% stop-loss |
| **Selection** | Auto based on gap (fade the gap) |
| **Capital** | ~₹55,000 minimum |
| **Max Loss** | ~₹6,000 (capped by hedge) |
| **Max Profit** | ~₹4,000 (credit received) |
| **Automation** | Fully automated, no intervention needed |
