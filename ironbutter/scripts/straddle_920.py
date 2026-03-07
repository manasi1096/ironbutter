#!/usr/bin/env python3
"""
9:20 AM Credit Spread Strategy Script
======================================
Executes a single credit spread at 9:20 AM on NIFTY based on gap direction.

Strategy:
  - Gap UP (>50 pts):   Put Credit Spread (Sell ATM PE + Buy OTM PE) - expects pullback
  - Gap DOWN (<-50 pts): Call Credit Spread (Sell ATM CE + Buy OTM CE) - expects bounce
  - Flat (within ±50):  Put Credit Spread (default, slight bullish bias)

Benefits:
  - Works with ~₹55K capital
  - Capped maximum loss
  - Adapts to market conditions ("fade the gap")

Usage:
    python3 straddle_920.py          # Execute spread
    python3 straddle_920.py monitor  # Monitor existing position

Cron entries (times in UTC, IST = UTC + 5:30):
    50 3 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/straddle_920.py >> /var/log/openalgo/straddle.log 2>&1
    */1 4-10 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/straddle_920.py monitor >> /var/log/openalgo/straddle.log 2>&1
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, date, timedelta
from datetime import time as dtime
from pathlib import Path

# Setup logging
log_dir = Path('/var/log/openalgo')
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'straddle.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
env_path = Path('/home/ubuntu/scripts/.env')
load_dotenv(env_path)

# Configuration
KITE_API_KEY = os.getenv('KITE_API_KEY')
KITE_ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN')

# Trading parameters
TRADING_SYMBOL = os.getenv('TRADING_SYMBOL', 'NIFTY')
QUANTITY = int(os.getenv('QUANTITY', 65))  # 1 lot of Nifty = 65
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', 40))  # 40% of max loss

# Gap threshold for spread selection (in points)
GAP_THRESHOLD = int(os.getenv('GAP_THRESHOLD', 50))

# Max gap threshold - skip trade if gap exceeds this (extreme moves don't mean-revert)
MAX_GAP_THRESHOLD = int(os.getenv('MAX_GAP_THRESHOLD', 200))

# Early profit exit - close when P&L reaches this % of credit received
EARLY_PROFIT_PCT = float(os.getenv('EARLY_PROFIT_PCT', 60))

# VIX threshold - skip trade if India VIX is above this level
VIX_THRESHOLD = float(os.getenv('VIX_THRESHOLD', 18))

# Skip expiry days (low premiums + high margin)
SKIP_EXPIRY_DAY = os.getenv('SKIP_EXPIRY_DAY', 'true').lower() == 'true'

# Exit time in IST - converted to UTC for VM (IST = UTC + 5:30)
EXIT_TIME_IST_STR = os.getenv('EXIT_TIME', '15:15')
exit_hour, exit_min = map(int, EXIT_TIME_IST_STR.split(':'))
utc_hour = exit_hour - 5
utc_min = exit_min - 30
if utc_min < 0:
    utc_min += 60
    utc_hour -= 1
EXIT_TIME = dtime(utc_hour, utc_min)

# Hedge distance (OTM strikes for protection)
HEDGE_DISTANCE = int(os.getenv('HEDGE_DISTANCE', 150))

# Retry configuration
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', 5))  # seconds between retries

# Strike step based on index
STRIKE_STEPS = {
    'NIFTY': 50,
    'BANKNIFTY': 100,
    'FINNIFTY': 50
}

# Position file
POSITION_FILE = Path('/home/ubuntu/scripts/current_position.json')

# Import Telegram notifier
try:
    from telegram_notifier import (
        notify_trade_entry, notify_trade_exit, notify_no_trade,
        notify_error, notify_position_update, send_telegram_message
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("Telegram notifier not available")

# Import CSV logger
try:
    from generate_csv import append_trade, append_failed
    CSV_AVAILABLE = True
except ImportError:
    CSV_AVAILABLE = False
    logger.warning("CSV logger not available")


def retry_api_call(func, *args, max_retries=None, retry_delay=None, **kwargs):
    """
    Retry an API call with exponential backoff.
    
    Args:
        func: Function to call
        *args: Positional arguments for func
        max_retries: Override default max retries
        retry_delay: Override default retry delay
        **kwargs: Keyword arguments for func
    
    Returns:
        Result of the function call
    
    Raises:
        Last exception if all retries fail
    """
    retries = max_retries if max_retries is not None else MAX_RETRIES
    delay = retry_delay if retry_delay is not None else RETRY_DELAY
    
    last_exception = None
    
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()
            
            # Don't retry for certain errors (authentication, insufficient funds, etc.)
            non_retryable = [
                'invalid api key',
                'invalid access token',
                'token expired',
                'insufficient funds',
                'margin',
                'rejected',
                'disabled for your account'
            ]
            
            if any(err in error_msg for err in non_retryable):
                logger.error(f"Non-retryable error: {e}")
                raise
            
            if attempt < retries - 1:
                wait_time = delay * (attempt + 1)  # Linear backoff
                logger.warning(f"API call failed (attempt {attempt + 1}/{retries}): {e}")
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"All {retries} attempts failed. Last error: {e}")
    
    raise last_exception


def get_kite_client():
    """Initialize and return Kite Connect client."""
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(KITE_ACCESS_TOKEN)
    return kite


def get_atm_strike(spot_price, symbol='NIFTY'):
    """Round spot price to nearest strike price."""
    step = STRIKE_STEPS.get(symbol, 50)
    return round(spot_price / step) * step


def get_previous_close(kite):
    """Get previous day's closing price."""
    spot_symbol = f"NSE:{TRADING_SYMBOL} 50" if TRADING_SYMBOL == "NIFTY" else f"NSE:{TRADING_SYMBOL}"
    quote = retry_api_call(kite.quote, [spot_symbol])
    return quote[spot_symbol]['ohlc']['close']


def determine_spread_type(current_price, previous_close):
    """
    Determine which spread to trade based on gap direction.
    
    Returns:
        'PUT' for Put Credit Spread (bullish/neutral - profits if market stays flat or goes up)
        'CALL' for Call Credit Spread (bearish/neutral - profits if market stays flat or goes down)
    """
    gap = current_price - previous_close
    gap_percent = (gap / previous_close) * 100
    
    logger.info(f"Previous Close: {previous_close}")
    logger.info(f"Current Price: {current_price}")
    logger.info(f"Gap: {gap:.2f} points ({gap_percent:.2f}%)")
    
    if gap > GAP_THRESHOLD:
        # Market gapped UP - expect pullback/mean reversion
        logger.info(f"Gap UP > {GAP_THRESHOLD} pts → PUT CREDIT SPREAD (expect pullback)")
        return 'PUT', gap, gap_percent
    elif gap < -GAP_THRESHOLD:
        # Market gapped DOWN - expect bounce/mean reversion
        logger.info(f"Gap DOWN < -{GAP_THRESHOLD} pts → CALL CREDIT SPREAD (expect bounce)")
        return 'CALL', gap, gap_percent
    else:
        # Flat open - default to Put spread (slight bullish bias)
        logger.info(f"Flat open (within ±{GAP_THRESHOLD} pts) → PUT CREDIT SPREAD (default)")
        return 'PUT', gap, gap_percent


def get_option_symbols(kite, atm_strike, spread_type):
    """
    Fetch option symbols for the selected spread type.
    
    Args:
        kite: KiteConnect instance
        atm_strike: ATM strike price
        spread_type: 'CALL' or 'PUT'
    
    Returns:
        dict with symbols for the spread
    """
    logger.info("Fetching NIFTY instruments from Kite...")
    instruments = retry_api_call(kite.instruments, 'NFO')
    nifty_opts = [i for i in instruments if i['name'] == 'NIFTY' and i['instrument_type'] in ['CE', 'PE']]
    
    today = date.today()
    expiries = sorted(set(i['expiry'] for i in nifty_opts if i['expiry'] >= today))
    
    if not expiries:
        raise ValueError("No upcoming NIFTY expiries found!")
    
    nearest_expiry = expiries[0]
    logger.info(f"Using expiry: {nearest_expiry}")
    
    expiry_opts = [i for i in nifty_opts if i['expiry'] == nearest_expiry]
    
    if spread_type == 'CALL':
        # Call Credit Spread: Sell ATM CE, Buy OTM CE (higher strike)
        otm_strike = atm_strike + HEDGE_DISTANCE
        atm_type = 'CE'
        otm_type = 'CE'
    else:
        # Put Credit Spread: Sell ATM PE, Buy OTM PE (lower strike)
        otm_strike = atm_strike - HEDGE_DISTANCE
        atm_type = 'PE'
        otm_type = 'PE'
    
    result = {
        'expiry_date': nearest_expiry,
        'spread_type': spread_type,
        'atm_strike': atm_strike,
        'otm_strike': otm_strike,
    }
    
    for opt in expiry_opts:
        strike = int(opt['strike'])
        opt_type = opt['instrument_type']
        symbol = opt['tradingsymbol']
        
        if strike == atm_strike and opt_type == atm_type:
            result['atm_symbol'] = symbol
        elif strike == otm_strike and opt_type == otm_type:
            result['otm_symbol'] = symbol
    
    required = ['atm_symbol', 'otm_symbol']
    missing = [k for k in required if k not in result]
    
    if missing:
        raise ValueError(f"Missing option symbols: {missing}")
    
    logger.info(f"ATM {atm_type} ({atm_strike}): {result['atm_symbol']}")
    logger.info(f"OTM {otm_type} ({otm_strike}): {result['otm_symbol']}")
    
    return result


def is_trading_day(notify=False):
    """Check if today is a trading day."""
    today = date.today()
    
    if today.weekday() >= 5:
        logger.info("Today is weekend. Skipping.")
        return False
    
    kill_switch = Path('/home/ubuntu/scripts/STOP_TRADING')
    if kill_switch.exists():
        logger.info("STOP_TRADING file found. Trading disabled.")
        if notify and TELEGRAM_AVAILABLE:
            notify_no_trade("STOP_TRADING kill switch is active")
        return False
    
    skip_file = Path('/home/ubuntu/scripts/skip_dates.txt')
    if skip_file.exists():
        skip_dates = skip_file.read_text().strip().split('\n')
        if str(today) in skip_dates:
            logger.info(f"Today in skip_dates.txt. Skipping.")
            if notify and TELEGRAM_AVAILABLE:
                notify_no_trade(f"Date {today} is in skip_dates.txt")
            return False
    
    return True


def verify_order(order_id, description):
    """Verify order status and return fill price."""
    kite = get_kite_client()
    time.sleep(1)  # Wait for order to process
    
    for attempt in range(5):
        orders = retry_api_call(kite.orders)
        for order in orders:
            if order['order_id'] == order_id:
                status = order['status']
                if status == 'COMPLETE':
                    fill_price = order['average_price']
                    logger.info(f"  ✓ {description}: FILLED @ ₹{fill_price}")
                    return True, fill_price
                elif status == 'REJECTED':
                    reason = order.get('status_message', 'Unknown')
                    logger.error(f"  ✗ {description}: REJECTED - {reason}")
                    return False, reason
                elif status in ['PENDING', 'OPEN', 'TRIGGER PENDING']:
                    logger.info(f"  ⏳ {description}: {status}")
                    time.sleep(1)
                    continue
        time.sleep(0.5)
    
    return False, "Order status unknown after timeout"


def rollback_orders(executed_orders):
    """Square off any partially executed orders."""
    if not executed_orders:
        return
        
    logger.warning(f"Rolling back {len(executed_orders)} executed orders...")
    kite = get_kite_client()
    
    for order in executed_orders:
        try:
            reverse_type = kite.TRANSACTION_TYPE_BUY if order['type'] == 'SELL' else kite.TRANSACTION_TYPE_SELL
            
            rollback_order = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=order['symbol'],
                transaction_type=reverse_type,
                quantity=QUANTITY,
                product=kite.PRODUCT_MIS,
                order_type=kite.ORDER_TYPE_MARKET
            )
            logger.info(f"  Rolled back {order['symbol']}: Order ID {rollback_order}")
        except Exception as e:
            logger.error(f"  Failed to rollback {order['symbol']}: {e}")


def is_expiry_day(kite):
    """Check if today is a NIFTY weekly expiry day."""
    instruments = retry_api_call(kite.instruments, 'NFO')
    nifty_opts = [i for i in instruments if i['name'] == 'NIFTY' and i['instrument_type'] in ['CE', 'PE']]
    today = date.today()
    expiries = sorted(set(i['expiry'] for i in nifty_opts if i['expiry'] >= today))
    if expiries and expiries[0] == today:
        return True
    return False


def check_vix(kite):
    """Fetch India VIX value."""
    try:
        vix_quote = retry_api_call(kite.quote, ['NSE:INDIA VIX'])
        vix_value = vix_quote['NSE:INDIA VIX']['last_price']
        return vix_value
    except Exception as e:
        logger.warning(f"Could not fetch VIX: {e}")
        return None


def execute_credit_spread():
    """Execute the 9:20 AM Credit Spread strategy."""
    logger.info("=" * 60)
    logger.info(f"EXECUTING 9:20 CREDIT SPREAD - {datetime.now()}")
    logger.info("=" * 60)
    
    if not is_trading_day(notify=True):
        return None
    
    if POSITION_FILE.exists():
        logger.warning("Position file already exists. Strategy may already be open.")
        return None
    
    try:
        kite = get_kite_client()
        
        # PRE-TRADE FILTERS
        
        # Filter 1: Skip expiry days
        if SKIP_EXPIRY_DAY and is_expiry_day(kite):
            reason = "Expiry day - low premiums and high margin, skipping"
            logger.info(f"SKIP: {reason}")
            if TELEGRAM_AVAILABLE:
                notify_no_trade(reason)
            if CSV_AVAILABLE:
                append_failed(str(date.today()), reason)
            return None
        
        # Filter 2: VIX check
        vix_value = check_vix(kite)
        if vix_value is not None:
            logger.info(f"India VIX: {vix_value:.2f} (threshold: {VIX_THRESHOLD})")
            if vix_value > VIX_THRESHOLD:
                reason = f"VIX too high ({vix_value:.1f} > {VIX_THRESHOLD}) - volatile market, skipping"
                logger.info(f"SKIP: {reason}")
                if TELEGRAM_AVAILABLE:
                    notify_no_trade(reason)
                if CSV_AVAILABLE:
                    append_failed(str(date.today()), reason)
                return None
        
        # Get current and previous close prices (with retry)
        spot_symbol = f"NSE:{TRADING_SYMBOL} 50" if TRADING_SYMBOL == "NIFTY" else f"NSE:{TRADING_SYMBOL}"
        logger.info(f"Fetching quote for {spot_symbol}...")
        quote = retry_api_call(kite.quote, [spot_symbol])
        current_price = quote[spot_symbol]['last_price']
        previous_close = quote[spot_symbol]['ohlc']['close']
        
        # Determine spread type based on gap
        spread_type, gap, gap_percent = determine_spread_type(current_price, previous_close)
        
        # Filter 3: Skip extreme gap days
        if abs(gap) > MAX_GAP_THRESHOLD:
            reason = f"Extreme gap ({gap:+.0f} pts > ±{MAX_GAP_THRESHOLD}) - news-driven move, skipping"
            logger.info(f"SKIP: {reason}")
            if TELEGRAM_AVAILABLE:
                notify_no_trade(reason)
            if CSV_AVAILABLE:
                append_failed(str(date.today()), reason)
            return None
        
        # Calculate ATM strike
        atm_strike = get_atm_strike(current_price, TRADING_SYMBOL)
        logger.info(f"ATM Strike: {atm_strike}")
        
        # Get option symbols (with retry)
        options = get_option_symbols(kite, atm_strike, spread_type)
        
        atm_symbol = options['atm_symbol']
        otm_symbol = options['otm_symbol']
        otm_strike = options['otm_strike']
        expiry = str(options['expiry_date'])
        
        # Get current option prices (with retry)
        logger.info("Fetching option prices...")
        option_prices = retry_api_call(kite.ltp, [f"NFO:{atm_symbol}", f"NFO:{otm_symbol}"])
        atm_price = option_prices[f"NFO:{atm_symbol}"]["last_price"]
        otm_price = option_prices[f"NFO:{otm_symbol}"]["last_price"]
        
        # Calculate credit and max loss
        spread_credit = atm_price - otm_price
        max_loss_per_unit = HEDGE_DISTANCE - spread_credit
        max_loss_total = max_loss_per_unit * QUANTITY
        total_credit = spread_credit * QUANTITY
        
        logger.info(f"ATM Price: {atm_price}")
        logger.info(f"OTM Price: {otm_price}")
        logger.info(f"Spread Credit: {spread_credit:.2f} (₹{total_credit:.0f} total)")
        logger.info(f"Max Loss: ₹{max_loss_total:.0f}")
        
        # Place orders - BUY HEDGE FIRST (critical for margin benefit)
        orders = {}
        executed_orders = []
        
        try:
            # Step 1: Buy OTM option (hedge)
            logger.info(f"Step 1/2: Buying {otm_symbol} (hedge)...")
            orders['buy_otm'] = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=otm_symbol,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=QUANTITY,
                product=kite.PRODUCT_MIS,
                order_type=kite.ORDER_TYPE_MARKET
            )
            logger.info(f"  Order ID: {orders['buy_otm']}")
            
            success, result = verify_order(orders['buy_otm'], f"Buy {otm_symbol}")
            if not success:
                raise Exception(f"Buy OTM failed: {result}")
            executed_orders.append({'symbol': otm_symbol, 'type': 'BUY', 'price': result})
            otm_fill_price = result
            
            time.sleep(0.3)
            
            # Step 2: Sell ATM option (now protected by hedge, lower margin)
            logger.info(f"Step 2/2: Selling {atm_symbol} (hedged)...")
            orders['sell_atm'] = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=atm_symbol,
                transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=QUANTITY,
                product=kite.PRODUCT_MIS,
                order_type=kite.ORDER_TYPE_MARKET
            )
            logger.info(f"  Order ID: {orders['sell_atm']}")
            
            success, result = verify_order(orders['sell_atm'], f"Sell {atm_symbol}")
            if not success:
                raise Exception(f"Sell ATM failed: {result}")
            executed_orders.append({'symbol': atm_symbol, 'type': 'SELL', 'price': result})
            atm_fill_price = result
            
            logger.info("Both orders executed successfully!")
            
            # Recalculate with actual fills
            spread_credit = atm_fill_price - otm_fill_price
            max_loss_per_unit = HEDGE_DISTANCE - spread_credit
            max_loss_total = max_loss_per_unit * QUANTITY
            total_credit = spread_credit * QUANTITY
            
        except Exception as order_error:
            logger.error(f"Order placement failed: {order_error}")
            rollback_orders(executed_orders)
            if TELEGRAM_AVAILABLE:
                notify_error("Order Placement Failed", str(order_error))
            raise
        
        # Store position
        position = {
            "date": str(date.today()),
            "time_opened": str(datetime.now()),
            "strategy": f"{spread_type}_CREDIT_SPREAD",
            "spread_type": spread_type,
            "symbol": TRADING_SYMBOL,
            "expiry": expiry,
            "atm_strike": atm_strike,
            "otm_strike": otm_strike,
            "hedge_distance": HEDGE_DISTANCE,
            "gap": gap,
            "gap_percent": gap_percent,
            "previous_close": previous_close,
            "entry_price": current_price,
            
            "atm_symbol": atm_symbol,
            "otm_symbol": otm_symbol,
            "orders": orders,
            
            "entry_atm_price": atm_fill_price,
            "entry_otm_price": otm_fill_price,
            "entry_spread_credit": spread_credit,
            "total_credit": total_credit,
            "max_loss": max_loss_total,
            
            "quantity": QUANTITY,
            "status": "OPEN"
        }
        
        with open(POSITION_FILE, 'w') as f:
            json.dump(position, f, indent=2)
        
        logger.info("=" * 60)
        logger.info(f"{spread_type} CREDIT SPREAD OPENED SUCCESSFULLY")
        logger.info(f"Credit: ₹{total_credit:.0f} | Max Loss: ₹{max_loss_total:.0f}")
        logger.info("=" * 60)
        
        # Send Telegram notification
        if TELEGRAM_AVAILABLE:
            spread_name = "Put Credit Spread" if spread_type == 'PUT' else "Call Credit Spread"
            gap_direction = "UP" if gap > 0 else "DOWN" if gap < 0 else "FLAT"
            message = (
                f"📊 <b>{spread_name} OPENED</b>\n\n"
                f"📅 {datetime.now().strftime('%d %b %Y')}\n"
                f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
                f"📈 <b>Gap:</b> {gap_direction} {abs(gap):.0f} pts ({gap_percent:+.2f}%)\n"
                f"🎯 <b>ATM Strike:</b> {atm_strike}\n"
                f"📍 <b>Expiry:</b> {expiry}\n\n"
                f"<b>Legs:</b>\n"
                f"  • Sell {atm_strike} {spread_type[0]}E @ ₹{atm_fill_price:.1f}\n"
                f"  • Buy {otm_strike} {spread_type[0]}E @ ₹{otm_fill_price:.1f}\n\n"
                f"💰 <b>Credit:</b> ₹{total_credit:,.0f}\n"
                f"🛡️ <b>Max Loss:</b> ₹{max_loss_total:,.0f}\n"
                f"📦 <b>Qty:</b> {QUANTITY}"
            )
            send_telegram_message(message)
        
        return position
        
    except Exception as e:
        logger.error(f"Error executing strategy: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        if TELEGRAM_AVAILABLE:
            notify_error("Strategy Execution Error", str(e))
        # Log failed trade to CSV
        if CSV_AVAILABLE:
            try:
                append_failed(str(date.today()), str(e)[:100])
                logger.info("Failed trade logged to CSV")
            except Exception as csv_err:
                logger.error(f"Failed to log to CSV: {csv_err}")
        return None


def get_current_spread_value(kite, position):
    """Calculate current spread value."""
    prices = retry_api_call(kite.ltp, [f"NFO:{position['atm_symbol']}", f"NFO:{position['otm_symbol']}"])
    
    current_atm = prices[f"NFO:{position['atm_symbol']}"]["last_price"]
    current_otm = prices[f"NFO:{position['otm_symbol']}"]["last_price"]
    current_spread = current_atm - current_otm
    
    return {
        'atm': current_atm,
        'otm': current_otm,
        'spread': current_spread
    }


def monitor_and_exit():
    """Monitor open position and exit on stop-loss or time."""
    logger.info(f"Monitoring position at {datetime.now()}")
    
    if not POSITION_FILE.exists():
        logger.info("No open position to monitor.")
        return
    
    try:
        with open(POSITION_FILE, 'r') as f:
            position = json.load(f)
    except json.JSONDecodeError:
        logger.error("Could not read position file.")
        return
    
    if position.get("date") != str(date.today()):
        logger.warning(f"Position is from {position.get('date')}, not today.")
        POSITION_FILE.unlink()
        return
    
    if position.get("status") != "OPEN":
        logger.info("Position is not open.")
        return
    
    try:
        kite = get_kite_client()
        
        # Get current spread value (with retry)
        current = get_current_spread_value(kite, position)
        
        entry_credit = position['entry_spread_credit']
        current_spread = current['spread']
        
        # P&L = (Entry credit - Current spread) * quantity
        # If spread widens (current > entry), we lose money
        unrealized_pnl = (entry_credit - current_spread) * position['quantity']
        pnl_percent = ((entry_credit - current_spread) / entry_credit) * 100 if entry_credit > 0 else 0
        
        max_loss = position.get('max_loss', float('inf'))
        stop_loss_threshold = max_loss * (STOP_LOSS_PERCENT / 100)
        
        total_credit = position.get('total_credit', 0)
        early_profit_target = total_credit * (EARLY_PROFIT_PCT / 100)
        
        logger.info(f"Entry Credit: {entry_credit:.2f}, Current Spread: {current_spread:.2f}")
        logger.info(f"Unrealized P&L: ₹{unrealized_pnl:.0f} ({pnl_percent:.1f}%)")
        logger.info(f"Stop Loss: ₹{stop_loss_threshold:.0f} ({STOP_LOSS_PERCENT:.0f}% of max loss ₹{max_loss:.0f})")
        logger.info(f"Profit Target: ₹{early_profit_target:.0f} ({EARLY_PROFIT_PCT:.0f}% of credit ₹{total_credit:.0f})")
        
        now = datetime.now().time()
        should_exit = False
        exit_reason = ""
        
        if unrealized_pnl <= -stop_loss_threshold:
            should_exit = True
            exit_reason = f"STOP LOSS - Lost ₹{abs(unrealized_pnl):.0f} (threshold: ₹{stop_loss_threshold:.0f})"
        elif unrealized_pnl >= early_profit_target and early_profit_target > 0:
            should_exit = True
            exit_reason = f"EARLY PROFIT - Made ₹{unrealized_pnl:.0f} (target: ₹{early_profit_target:.0f} = {EARLY_PROFIT_PCT:.0f}% of credit)"
        elif now >= EXIT_TIME:
            should_exit = True
            exit_reason = f"TIME EXIT - {EXIT_TIME_IST_STR} IST"
        
        if should_exit:
            logger.info("=" * 60)
            logger.info(f"EXITING: {exit_reason}")
            logger.info("=" * 60)
            
            exit_orders = {}
            
            # Close short (buy back ATM)
            exit_orders['close_atm'] = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=position['atm_symbol'],
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=position['quantity'],
                product=kite.PRODUCT_MIS,
                order_type=kite.ORDER_TYPE_MARKET
            )
            logger.info(f"Close ATM: {exit_orders['close_atm']}")
            time.sleep(0.2)
            
            # Close long (sell OTM)
            exit_orders['close_otm'] = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=position['otm_symbol'],
                transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=position['quantity'],
                product=kite.PRODUCT_MIS,
                order_type=kite.ORDER_TYPE_MARKET
            )
            logger.info(f"Close OTM: {exit_orders['close_otm']}")
            
            final_pnl = (entry_credit - current_spread) * position['quantity']
            
            position['status'] = 'CLOSED'
            position['exit_reason'] = exit_reason
            position['exit_time'] = str(datetime.now())
            position['exit_orders'] = exit_orders
            position['exit_atm_price'] = current['atm']
            position['exit_otm_price'] = current['otm']
            position['realized_pnl'] = final_pnl
            
            # Save to history
            history_dir = Path('/home/ubuntu/scripts/trade_history')
            history_dir.mkdir(parents=True, exist_ok=True)
            history_file = history_dir / f"{position['date']}_credit_spread.json"
            
            with open(history_file, 'w') as f:
                json.dump(position, f, indent=2)
            
            POSITION_FILE.unlink()

            # Append to CSV
            if CSV_AVAILABLE:
                try:
                    append_trade(position)
                    logger.info("Trade appended to CSV")
                except Exception as csv_err:
                    logger.error(f"Failed to append to CSV: {csv_err}")

            logger.info(f"POSITION CLOSED - P&L: ₹{final_pnl:.0f}")
            
            if TELEGRAM_AVAILABLE:
                pnl_emoji = "📈" if final_pnl > 0 else "📉" if final_pnl < 0 else "➖"
                spread_type = position.get('spread_type', 'UNKNOWN')
                message = (
                    f"{pnl_emoji} <b>{spread_type} Credit Spread CLOSED</b>\n\n"
                    f"📅 {datetime.now().strftime('%d %b %Y')}\n"
                    f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
                    f"🚪 <b>Exit Reason:</b> {exit_reason}\n\n"
                    f"💵 <b>Entry Credit:</b> ₹{position['total_credit']:,.0f}\n"
                    f"💰 <b>P&L:</b> ₹{final_pnl:,.0f}\n\n"
                    f"📍 ATM: ₹{position['entry_atm_price']:.1f} → ₹{current['atm']:.1f}\n"
                    f"📍 OTM: ₹{position['entry_otm_price']:.1f} → ₹{current['otm']:.1f}"
                )
                send_telegram_message(message)
        else:
            logger.info(f"Position open. P&L: ₹{unrealized_pnl:.0f} ({pnl_percent:.1f}%)")
            
    except Exception as e:
        logger.error(f"Error monitoring: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        if TELEGRAM_AVAILABLE:
            notify_error("Monitoring Error", str(e))


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        monitor_and_exit()
    else:
        execute_credit_spread()


if __name__ == "__main__":
    main()
