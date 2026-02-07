#!/usr/bin/env python3
"""
Daily Summary Script
====================
Sends end-of-day report to Telegram with:
- Opening balance
- Closing balance  
- Day's P&L
- Breakdown of profits and losses by position

Run via cron at 3:35 PM IST (after market close):
35 10 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/daily_summary.py
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
env_path = Path('/home/ubuntu/scripts/.env')
load_dotenv(env_path)

from telegram_notifier import notify_eod_report, notify_error


def get_daily_summary():
    """Fetch account data and positions P&L from Kite."""
    from kiteconnect import KiteConnect
    
    kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
    kite.set_access_token(os.getenv('KITE_ACCESS_TOKEN'))
    
    # Get margin/balance info
    margins = kite.margins()
    equity = margins.get('equity', {})
    available = equity.get('available', {})
    utilised = equity.get('utilised', {})
    
    opening_balance = available.get('opening_balance', 0)
    current_balance = available.get('live_balance', 0)
    
    # Realized P&L pending settlement
    pending_settlement = utilised.get('m2m_realised', 0)
    
    # Get positions P&L breakdown
    positions = kite.positions()
    day_positions = positions.get('day', [])
    
    positions_pnl = []
    total_pnl = 0
    
    for p in day_positions:
        pnl = p.get('pnl', 0)
        if pnl != 0:
            # Clean up symbol name for display
            symbol = p.get('tradingsymbol', 'Unknown')
            # Make it more readable (e.g., NIFTY2620325400CE -> NIFTY 25400 CE)
            display_symbol = symbol
            if 'NIFTY' in symbol:
                try:
                    # Extract strike and type
                    if symbol.startswith('NIFTY'):
                        rest = symbol[5:]  # Remove 'NIFTY'
                        # Format: YYMMDDSSSSSTT (e.g., 2620325400CE)
                        strike = rest[-7:-2]  # Last 5 digits before CE/PE
                        opt_type = rest[-2:]  # CE or PE
                        display_symbol = f"NIFTY {int(strike)} {opt_type}"
                except:
                    pass
            
            positions_pnl.append({
                'symbol': display_symbol,
                'pnl': pnl
            })
            total_pnl += pnl
    
    # Sort by absolute P&L (biggest impact first)
    positions_pnl.sort(key=lambda x: abs(x['pnl']), reverse=True)
    
    return {
        'opening_balance': opening_balance,
        'current_balance': current_balance,
        'day_pnl': total_pnl,
        'positions_pnl': positions_pnl,
        'pending_settlement': pending_settlement
    }


def main():
    """Main entry point."""
    logger.info("=" * 50)
    logger.info(f"DAILY SUMMARY - {datetime.now()}")
    logger.info("=" * 50)
    
    try:
        # Get data from Kite
        data = get_daily_summary()
        
        logger.info(f"Opening Balance: {data['opening_balance']}")
        logger.info(f"Current Balance: {data['current_balance']}")
        logger.info(f"Day P&L: {data['day_pnl']}")
        logger.info(f"Positions: {len(data['positions_pnl'])}")
        
        # Send Telegram report
        success = notify_eod_report(
            opening_balance=data['opening_balance'],
            current_balance=data['current_balance'],
            day_pnl=data['day_pnl'],
            positions_pnl=data['positions_pnl'],
            pending_settlement=data['pending_settlement']
        )
        
        if success:
            logger.info("✅ Daily summary sent to Telegram")
        else:
            logger.error("❌ Failed to send Telegram message")
            
    except Exception as e:
        logger.error(f"Error generating daily summary: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to send error notification
        try:
            notify_error("Daily Summary Error", str(e))
        except:
            pass


if __name__ == "__main__":
    main()
