# Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TRADING FLOW                                   │
└─────────────────────────────────────────────────────────────────────────┘

     ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
     │   8:30 AM    │         │   9:20 AM    │         │  Every 1min  │
     │  Auto Login  │────────►│   Execute    │────────►│   Monitor    │
     │              │         │   Strategy   │         │   Position   │
     └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
            │                        │                        │
            ▼                        ▼                        ▼
     ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
     │  Playwright  │         │  Kite API    │         │  Kite API    │
     │  Browser     │         │  Place Order │         │  Get LTP     │
     └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
            │                        │                        │
            ▼                        ▼                        ▼
     ┌──────────────────────────────────────────────────────────────┐
     │                      ZERODHA / NSE                           │
     └──────────────────────────────────────────────────────────────┘
```

## Components

### 1. Auto Login Script (`auto_login.py`)

**Purpose**: Refresh Kite access token daily (required due to SEBI regulations)

**Flow**:
```
1. Launch headless Chromium browser (Playwright)
2. Navigate to Kite Connect login URL
3. Enter User ID and Password
4. Generate TOTP using pyotp library
5. Enter TOTP code
6. Capture request_token from redirect URL
7. Exchange request_token for access_token via Kite API
8. Save access_token to .env file
```

**Key Libraries**:
- `playwright` - Browser automation
- `pyotp` - TOTP code generation
- `kiteconnect` - Zerodha API SDK

### 2. Strategy Script (`straddle_920.py`)

**Purpose**: Execute and manage Iron Butterfly trades

**Execution Flow (9:20 AM)**:
```
1. Get NIFTY spot price via Kite API
2. Calculate ATM strike (round to nearest 50)
3. Calculate OTM strikes (±150 points)
4. Place 4 orders:
   - SELL ATM Call
   - BUY OTM Call (hedge)
   - SELL ATM Put
   - BUY OTM Put (hedge)
5. Save position to JSON file
```

**Monitoring Flow (Every 1 min)**:
```
1. Load position from JSON file
2. Get current prices of all 4 legs
3. Calculate unrealized P&L
4. Check exit conditions:
   - Stop-loss: Loss > 30% of credit
   - Time exit: Time >= 3:15 PM
5. If exit triggered:
   - Close all 4 legs
   - Save to trade history
   - Delete current position file
```

### 3. Configuration (`.env`)

```
# API Credentials
KITE_API_KEY=xxx
KITE_API_SECRET=xxx
KITE_USER_ID=xxx
KITE_PASSWORD=xxx
TOTP_SECRET=xxx

# Auto-updated by login script
KITE_ACCESS_TOKEN=xxx

# Trading Parameters
TRADING_SYMBOL=NIFTY
QUANTITY=50
STOP_LOSS_PERCENT=30
EXIT_TIME=15:15
HEDGE_DISTANCE=150
```

## Data Flow

### Position File Structure (`current_position.json`)

```json
{
  "date": "2026-01-27",
  "time_opened": "2026-01-27 09:20:15",
  "strategy": "IRON_BUTTERFLY",
  "symbol": "NIFTY",
  "expiry": "30JAN",
  "atm_strike": 23850,
  "otm_call_strike": 24000,
  "otm_put_strike": 23700,
  "hedge_distance": 150,
  "atm_ce_symbol": "NIFTY30JAN23850CE",
  "atm_pe_symbol": "NIFTY30JAN23850PE",
  "otm_ce_symbol": "NIFTY30JAN24000CE",
  "otm_pe_symbol": "NIFTY30JAN23700PE",
  "entry_total_credit": 140,
  "max_loss": 500,
  "quantity": 50,
  "status": "OPEN"
}
```

### Trade History File Structure

```json
{
  "date": "2026-01-27",
  "strategy": "IRON_BUTTERFLY",
  "entry_total_credit": 140,
  "exit_prices": {...},
  "realized_pnl": 3500,
  "exit_reason": "TIME EXIT - 15:15:00",
  "status": "CLOSED"
}
```

## Cron Schedule

| Cron Expression | Time (IST) | Action |
|-----------------|------------|--------|
| `0 3 * * 1-5` | 8:30 AM | Auto login |
| `50 3 * * 1-5` | 9:20 AM | Execute strategy |
| `*/1 4-10 * * 1-5` | 9:30 AM - 3:30 PM | Monitor position |

**Note**: Cron uses UTC. IST = UTC + 5:30

## Error Handling

### Auto Login Failures
- Screenshots saved to `/var/log/openalgo/`
- Retries not implemented (relies on next day's cron)
- Check logs for debugging

### Order Failures
- Logged with full error details
- Position file not created if entry fails
- Partial fills not handled (market orders usually fill completely)

### Monitoring Failures
- Errors logged but monitoring continues
- Position file remains until successful exit

## Security Considerations

1. **Credentials**: Stored in `.env` with 600 permissions
2. **SSH**: Key-based authentication only
3. **VM Firewall**: Only port 22 open
4. **No external API exposure**: Scripts run locally on VM
5. **TOTP Secret**: Required for auto-login (against Zerodha ToS technically)

## Scaling Considerations

Current setup is for single-user, single-strategy. To scale:

1. **Multiple Strategies**: Add separate scripts with different cron times
2. **Multiple Indices**: Modify TRADING_SYMBOL in .env
3. **Position Sizing**: Adjust QUANTITY parameter
4. **Database**: Replace JSON files with SQLite/PostgreSQL for history

