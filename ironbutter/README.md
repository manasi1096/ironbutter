# 9:20 AM Credit Spread Trading System

An automated options trading system that executes a **single credit spread** on NIFTY at 9:20 AM IST daily. The spread direction is auto-selected based on market gap at open.

## Features

- **Fully Automated** - No manual intervention required
- **Adaptive Strategy** - Selects Put or Call spread based on gap direction
- **Risk Managed** - Capped maximum loss with hedge protection
- **Stop Loss** - Automatic exit at 50% of max loss
- **Time Exit** - Auto-closes at 3:15 PM IST
- **Telegram Alerts** - Real-time notifications for all events
- **Daily Reports** - EOD summary with P&L breakdown

## Strategy Overview

| Condition | Spread Type | Rationale |
|-----------|-------------|-----------|
| Gap UP > 50 pts | Put Credit Spread | Expect pullback |
| Gap DOWN > 50 pts | Call Credit Spread | Expect bounce |
| Flat (±50 pts) | Put Credit Spread | Slight bullish bias |

## Requirements

- **Capital**: ~₹55,000 minimum
- **Broker**: Zerodha (Kite Connect API)
- **Server**: Oracle Cloud Free Tier VM (or any Linux server)
- **Python**: 3.8+

## Quick Start

1. **Clone & Setup**
   ```bash
   git clone <repo-url>
   cd oa-shareable
   pip3 install -r scripts/requirements.txt
   playwright install chromium
   ```

2. **Configure Credentials**
   ```bash
   cp scripts/.env.example scripts/.env
   # Edit .env with your credentials
   ```

3. **Test Connection**
   ```bash
   python3 scripts/telegram_notifier.py  # Test Telegram
   python3 scripts/auto_login.py         # Test login
   ```

4. **Deploy to VM**
   ```bash
   scp -r scripts/ ubuntu@your-vm:/home/ubuntu/
   ssh ubuntu@your-vm
   ./setup_vm.sh
   ```

## Documentation

- [STRATEGY.md](STRATEGY.md) - Detailed strategy explanation
- [SETUP.md](SETUP.md) - Full setup instructions
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues & fixes

## File Structure

```
oa-shareable/
├── README.md
├── STRATEGY.md          # Strategy documentation
├── SETUP.md             # Setup instructions
├── ARCHITECTURE.md      # System architecture
├── TROUBLESHOOTING.md   # Debugging guide
├── setup_vm.sh          # VM setup script
└── scripts/
    ├── .env.example     # Template for credentials
    ├── requirements.txt # Python dependencies
    ├── auto_login.py    # Daily login automation
    ├── straddle_920.py  # Main strategy script
    ├── telegram_notifier.py  # Telegram notifications
    └── daily_summary.py # EOD report generator
```

## Typical Results

| Metric | Value |
|--------|-------|
| Max Profit | ~₹4,000 (credit received) |
| Max Loss | ~₹6,000 (capped by hedge) |
| Stop Loss | ~₹3,000 (50% of max) |
| Expected Win Rate | 60-70% |

## Disclaimer

This is an educational project. Options trading involves significant risk. Past performance does not guarantee future results. Use at your own risk. The author is not responsible for any financial losses.

## License

MIT License - Feel free to modify and use.
