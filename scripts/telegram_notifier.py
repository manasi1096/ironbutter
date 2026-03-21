#!/usr/bin/env python3
"""
Telegram Notification Module
============================
Sends real-time alerts to your Telegram chat for:
  - Trade entries
  - Trade exits  
  - Stop-loss triggers
  - Daily P&L summaries
  - Errors and warnings

Setup:
  1. Create a bot via @BotFather on Telegram
  2. Get your chat ID via @userinfobot
  3. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env
"""

import os
import requests
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Load config
from dotenv import load_dotenv
env_path = Path('/home/ubuntu/scripts/.env')
load_dotenv(env_path)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_ENABLED = TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID


def send_telegram_message(message: str, parse_mode: str = 'HTML') -> bool:
    """
    Send a message via Telegram bot.
    
    Args:
        message: The message text (supports HTML formatting)
        parse_mode: 'HTML' or 'Markdown'
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not TELEGRAM_ENABLED:
        logger.debug("Telegram not configured, skipping notification")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': parse_mode
        }
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            logger.debug("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def format_currency(amount: float) -> str:
    """Format amount as Indian currency."""
    if amount >= 0:
        return f"₹{amount:,.0f}"
    else:
        return f"-₹{abs(amount):,.0f}"


def notify_login_success():
    """Send notification when daily login succeeds."""
    message = (
        "🔓 <b>Login Successful</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
        "✅ Access token refreshed. Ready for trading!"
    )
    return send_telegram_message(message)


def notify_login_failed(error: str = None):
    """Send notification when daily login fails."""
    message = (
        "🔴 <b>Login FAILED</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
        "⚠️ Could not refresh access token!\n"
        "Trading will NOT work today.\n\n"
        f"Error: <code>{error or 'Unknown'}</code>"
    )
    return send_telegram_message(message)


def notify_trade_entry(position: dict):
    """
    Send notification when Iron Butterfly is opened.
    
    Args:
        position: Position dictionary with trade details
    """
    atm_strike = position.get('atm_strike', 'N/A')
    credit = position.get('entry_total_credit', 0) * position.get('quantity', 50)
    max_loss = position.get('max_loss', 0)
    
    message = (
        "🦋 <b>Iron Butterfly OPENED</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
        
        f"📊 <b>Index:</b> {position.get('symbol', 'NIFTY')}\n"
        f"🎯 <b>ATM Strike:</b> {atm_strike}\n"
        f"📍 <b>Expiry:</b> {position.get('expiry', 'N/A')}\n\n"
        
        f"<b>Legs:</b>\n"
        f"  • Sell {atm_strike} CE @ {position.get('entry_atm_ce_price', 0):.1f}\n"
        f"  • Buy {position.get('otm_call_strike', 'N/A')} CE @ {position.get('entry_otm_ce_price', 0):.1f}\n"
        f"  • Sell {atm_strike} PE @ {position.get('entry_atm_pe_price', 0):.1f}\n"
        f"  • Buy {position.get('otm_put_strike', 'N/A')} PE @ {position.get('entry_otm_pe_price', 0):.1f}\n\n"
        
        f"💰 <b>Credit Received:</b> {format_currency(credit)}\n"
        f"🛡️ <b>Max Loss (capped):</b> {format_currency(max_loss)}\n"
        f"📦 <b>Qty:</b> {position.get('quantity', 50)} units"
    )
    return send_telegram_message(message)


def notify_trade_exit(position: dict):
    """
    Send notification when Iron Butterfly is closed.
    
    Args:
        position: Position dictionary with full trade details
    """
    pnl = position.get('realized_pnl', 0)
    exit_reason = position.get('exit_reason', 'Unknown')
    
    # Determine emoji based on P&L
    if pnl > 0:
        pnl_emoji = "📈"
        result_text = "PROFIT"
    elif pnl < 0:
        pnl_emoji = "📉"
        result_text = "LOSS"
    else:
        pnl_emoji = "➖"
        result_text = "BREAKEVEN"
    
    # Determine exit emoji
    if 'STOP LOSS' in exit_reason:
        exit_emoji = "🚨"
    else:
        exit_emoji = "⏰"
    
    entry_credit = position.get('entry_total_credit', 0) * position.get('quantity', 50)
    
    message = (
        f"{pnl_emoji} <b>Iron Butterfly CLOSED</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
        
        f"{exit_emoji} <b>Exit Reason:</b> {exit_reason}\n\n"
        
        f"💵 <b>Entry Credit:</b> {format_currency(entry_credit)}\n"
        f"💰 <b>Today's P&L:</b> {format_currency(pnl)}\n"
        f"📊 <b>Result:</b> {result_text}\n\n"
        
        f"📍 Trade Details:\n"
        f"  • Symbol: {position.get('symbol', 'NIFTY')}\n"
        f"  • ATM Strike: {position.get('atm_strike', 'N/A')}\n"
        f"  • Open Time: {position.get('time_opened', 'N/A')[:19]}\n"
        f"  • Close Time: {position.get('exit_time', 'N/A')[:19]}"
    )
    return send_telegram_message(message)


def notify_position_update(position: dict, current: dict, pnl: float, pnl_percent: float):
    """
    Send periodic position update (optional, called less frequently).
    Only sends if there's a significant change.
    
    Args:
        position: Original position
        current: Current price data
        pnl: Current unrealized P&L
        pnl_percent: P&L as percentage
    """
    # Determine status emoji
    if pnl_percent > 0:
        status = "🟢"
    elif pnl_percent > -15:
        status = "🟡"
    else:
        status = "🔴"
    
    message = (
        f"{status} <b>Position Update</b>\n\n"
        f"⏰ {datetime.now().strftime('%H:%M')} IST\n\n"
        f"💰 <b>Unrealized P&L:</b> {format_currency(pnl)} ({pnl_percent:+.1f}%)\n"
        f"🎯 <b>ATM Strike:</b> {position.get('atm_strike', 'N/A')}\n\n"
        f"Current Prices:\n"
        f"  • ATM CE: {current.get('atm_ce', 0):.1f}\n"
        f"  • ATM PE: {current.get('atm_pe', 0):.1f}"
    )
    return send_telegram_message(message)


def notify_no_trade(reason: str):
    """Send notification when trade is skipped."""
    message = (
        "⏸️ <b>Trade Skipped</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
        f"📌 <b>Reason:</b> {reason}"
    )
    return send_telegram_message(message)


def notify_error(error_type: str, error_msg: str):
    """Send notification for critical errors."""
    message = (
        "🚨 <b>ERROR ALERT</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
        f"❌ <b>Type:</b> {error_type}\n"
        f"📝 <b>Details:</b>\n<code>{error_msg[:500]}</code>\n\n"
        "⚠️ Manual intervention may be required!"
    )
    return send_telegram_message(message)


def notify_daily_summary(trades: list):
    """
    Send end-of-day summary (legacy function).
    """
    if not trades:
        message = (
            "📋 <b>Daily Summary</b>\n\n"
            f"📅 {datetime.now().strftime('%d %b %Y')}\n\n"
            "No trades executed today."
        )
        return send_telegram_message(message)
    
    total_pnl = sum(t.get('realized_pnl', 0) for t in trades)
    wins = sum(1 for t in trades if t.get('realized_pnl', 0) > 0)
    losses = sum(1 for t in trades if t.get('realized_pnl', 0) < 0)
    
    pnl_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➖"
    
    message = (
        f"📋 <b>Daily Summary</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}\n\n"
        f"📊 <b>Trades:</b> {len(trades)}\n"
        f"✅ <b>Winners:</b> {wins}\n"
        f"❌ <b>Losers:</b> {losses}\n\n"
        f"{pnl_emoji} <b>Total P&L:</b> {format_currency(total_pnl)}"
    )
    return send_telegram_message(message)


def notify_eod_report(opening_balance: float, current_balance: float, day_pnl: float, 
                      positions_pnl: list, pending_settlement: float = 0):
    """
    Send comprehensive end-of-day report with P&L breakdown.
    
    Args:
        opening_balance: Account balance at start of day
        current_balance: Current available balance
        day_pnl: Total realized P&L for the day
        positions_pnl: List of dicts with symbol, pnl for each position
        pending_settlement: P&L pending settlement (credited next trading day)
    """
    # Determine overall emoji
    if day_pnl > 0:
        pnl_emoji = "📈"
        result = "PROFIT"
    elif day_pnl < 0:
        pnl_emoji = "📉"
        result = "LOSS"
    else:
        pnl_emoji = "➖"
        result = "NO CHANGE"
    
    # Build P&L breakdown
    winners = []
    losers = []
    for p in positions_pnl:
        symbol = p.get('symbol', 'Unknown')
        pnl = p.get('pnl', 0)
        if pnl > 0:
            winners.append(f"  ✅ {symbol}: {format_currency(pnl)}")
        elif pnl < 0:
            losers.append(f"  ❌ {symbol}: {format_currency(pnl)}")
    
    breakdown = ""
    if winners:
        breakdown += "\n<b>Profitable:</b>\n" + "\n".join(winners)
    if losers:
        breakdown += "\n\n<b>Loss-making:</b>\n" + "\n".join(losers)
    if not winners and not losers:
        breakdown = "\nNo positions traded today."
    
    # Calculate expected closing (after settlement)
    expected_closing = opening_balance + day_pnl
    
    message = (
        f"{pnl_emoji} <b>END OF DAY REPORT</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y (%A)')}\n\n"
        
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💼 <b>ACCOUNT SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌅 Opening Balance: {format_currency(opening_balance)}\n"
        f"💰 Day's P&L: {format_currency(day_pnl)}\n"
        f"🌆 Expected Closing: {format_currency(expected_closing)}\n"
    )
    
    if pending_settlement > 0:
        message += f"⏳ Pending Settlement: {format_currency(pending_settlement)}\n"
    
    message += (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>P&L BREAKDOWN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
        f"{breakdown}\n\n"
        
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏁 <b>RESULT: {result}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    return send_telegram_message(message)


def notify_order_failed(order_type: str, symbol: str, reason: str):
    """Send notification when an order fails/is rejected."""
    message = (
        "🚫 <b>ORDER REJECTED</b>\n\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')} IST\n\n"
        f"📝 <b>Order:</b> {order_type} {symbol}\n"
        f"❌ <b>Reason:</b> {reason}\n\n"
        "⚠️ Strategy may be partially executed!"
    )
    return send_telegram_message(message)


def test_telegram():
    """Send a test message to verify configuration."""
    message = (
        "🤖 <b>Telegram Bot Connected!</b>\n\n"
        f"⏰ {datetime.now().strftime('%d %b %Y %H:%M:%S')} IST\n\n"
        "✅ Your trading alerts are now active.\n"
        "You will receive notifications for:\n"
        "  • Trade entries & exits\n"
        "  • Stop-loss triggers\n"
        "  • Login status\n"
        "  • Errors & warnings"
    )
    return send_telegram_message(message)


if __name__ == "__main__":
    # Test the connection
    if TELEGRAM_ENABLED:
        print("Testing Telegram connection...")
        if test_telegram():
            print("✅ Test message sent successfully!")
        else:
            print("❌ Failed to send test message")
    else:
        print("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")

