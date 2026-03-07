# 9:20 AM Credit Spread Strategy (v2)

## Overview

An automated options trading system that executes a **single credit spread** on NIFTY at 9:20 AM IST daily. The spread direction is auto-selected based on market gap at open.

---

## Pre-Trade Filters (NEW in v2)

Before placing any trade, the system runs 3 safety checks:

### 1. Expiry Day Skip
If today is a NIFTY weekly expiry day, **skip the trade**. Premiums are too low and margin requirements spike.

### 2. VIX Filter
If India VIX > 18, **skip the trade**. High volatility means wider intraday swings and higher chance of loss.

### 3. Extreme Gap Filter
If the opening gap exceeds 200 points in either direction, **skip the trade**. Extreme gaps are news-driven and don't mean-revert reliably.

```
Filter Flow:
  Is expiry day?     → YES → Skip
  VIX > 18?          → YES → Skip
  Gap > ±200 pts?    → YES → Skip
  All clear           → Proceed to trade
```

---

## Auto-Selection Logic

At 9:20 AM, the system checks the gap between current price and previous day's close:

```
Gap = Current Price - Previous Close

If Gap > +50 points:  → PUT Credit Spread (expect pullback)
If Gap < -50 points:  → CALL Credit Spread (expect bounce)
If Gap within ±50:    → PUT Credit Spread (default)
```

---

## Entry Details

### Timing
- **Entry:** 9:20 AM IST (3:50 AM UTC)

### Order Sequence (Critical for Margin)
1. **Buy OTM option first** (hedge) - uses cash for premium
2. **Sell ATM option second** - now recognized as spread, lower margin

### Strike Selection
- **ATM Strike:** Rounded to nearest 50
- **OTM Strike:** ATM ± 150 points (hedge distance)

### Quantity
- **1 lot of NIFTY = 65 units**

---

## Exit Rules (Updated in v2)

Three exit conditions, checked every minute:

### 1. Early Profit Exit (NEW)
If unrealized P&L reaches **60% of credit received**, exit immediately.
- Example: Credit = 3,800. If P&L hits +2,280 at 1 PM, close now.
- Locks in gains instead of risking a reversal.

### 2. Stop-Loss Exit (Tightened)
Triggers at **40% of maximum loss** (was 50%).
- Example: If max loss = 6,000, stop-loss at -2,400 (was -3,000).

### 3. Time-Based Exit
Position auto-closes at **3:15 PM IST** if neither profit target nor stop-loss hit.

```
Exit Priority:
  P&L <= -40% of max loss  → STOP LOSS (exit immediately)
  P&L >= 60% of credit     → EARLY PROFIT (exit immediately)
  Time >= 3:15 PM IST      → TIME EXIT (close everything)
```

---

## Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| STOP_LOSS_PERCENT | 40 | Stop-loss at 40% of max loss |
| EARLY_PROFIT_PCT | 60 | Take profit at 60% of credit |
| GAP_THRESHOLD | 50 | Min gap for directional spread |
| MAX_GAP_THRESHOLD | 200 | Skip if gap exceeds this |
| VIX_THRESHOLD | 18 | Skip if VIX above this |
| SKIP_EXPIRY_DAY | true | Auto-skip expiry days |
| HEDGE_DISTANCE | 150 | OTM strike distance |
| QUANTITY | 65 | 1 NIFTY lot |

All configurable via `.env` file.

---

## Risk Management

### Capped Maximum Loss
The OTM hedge caps the maximum loss regardless of market movement.

### Position Sizing
- 1 lot only (65 units)
- Single spread per day

### Capital Requirement
- Minimum: ~50,000
- Recommended: 55,000 - 60,000

---

## Infrastructure

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
├── .env                    # Credentials and config
├── straddle_920.py         # Main strategy script
├── auto_login.py           # Daily login automation
├── telegram_notifier.py    # Notification functions
├── daily_summary.py        # EOD report script
├── generate_csv.py         # CSV trade logger
├── trade_history.csv       # P&L tracking
├── current_position.json   # Active position (if any)
├── skip_dates.txt          # Dates to skip trading
├── STOP_TRADING            # Kill switch file (create to stop)
└── trade_history/          # Completed trade JSONs
```

---

## Changelog

| Version | Changes |
|---------|---------|
| 1.0 | Initial Iron Butterfly setup |
| 1.1 | Fixed order sequence (buy hedge first) |
| 1.2 | Switched to single credit spread |
| 1.3 | Added gap-based auto-selection |
| 1.4 | Fixed timezone (UTC vs IST) |
| 1.5 | Added retry logic for API failures |
| 1.6 | Added CSV trade logging |
| **2.0** | **5 strategy improvements:** |
|     | - Skip expiry days automatically |
|     | - Early profit exit at 60% of credit |
|     | - Tightened stop-loss from 50% to 40% |
|     | - Skip extreme gaps (>200 pts) |
|     | - VIX filter (skip when VIX > 18) |
