#!/usr/bin/env python3
"""
Generate/Update Trade History CSV
=================================
Creates and maintains a CSV file with daily P&L data.

Can be run standalone to rebuild CSV from trade history JSON files,
or called from other scripts to append a single row.

CSV Location: /home/ubuntu/scripts/trade_history.csv
"""

import csv
import json
import os
import glob
from datetime import datetime, date
from pathlib import Path

CSV_FILE = Path('/home/ubuntu/scripts/trade_history.csv')
HISTORY_DIR = Path('/home/ubuntu/scripts/trade_history')

CSV_HEADERS = [
    'date',
    'day',
    'strategy',
    'spread_type',
    'atm_strike',
    'otm_strike',
    'expiry',
    'gap_points',
    'gap_percent',
    'entry_price',
    'entry_atm_price',
    'entry_otm_price',
    'exit_atm_price',
    'exit_otm_price',
    'credit_received',
    'max_loss',
    'realized_pnl',
    'result',
    'exit_reason',
    'cumulative_pnl'
]


def trade_json_to_row(data, cumulative_pnl):
    """Convert a trade history JSON dict to a CSV row dict."""
    pnl = data.get('realized_pnl', 0)
    cumulative_pnl += pnl
    
    trade_date = data.get('date', '')
    try:
        day_name = datetime.strptime(trade_date, '%Y-%m-%d').strftime('%A')
    except:
        day_name = ''
    
    if pnl > 0:
        result = 'WIN'
    elif pnl < 0:
        result = 'LOSS'
    else:
        result = 'FLAT'
    
    return {
        'date': trade_date,
        'day': day_name,
        'strategy': data.get('strategy', ''),
        'spread_type': data.get('spread_type', ''),
        'atm_strike': data.get('atm_strike', ''),
        'otm_strike': data.get('otm_strike', ''),
        'expiry': data.get('expiry', ''),
        'gap_points': round(data.get('gap', 0), 1),
        'gap_percent': round(data.get('gap_percent', 0), 2),
        'entry_price': data.get('entry_price', ''),
        'entry_atm_price': data.get('entry_atm_price', ''),
        'entry_otm_price': data.get('entry_otm_price', ''),
        'exit_atm_price': data.get('exit_atm_price', ''),
        'exit_otm_price': data.get('exit_otm_price', ''),
        'credit_received': round(data.get('total_credit', 0), 0),
        'max_loss': round(data.get('max_loss', 0), 0),
        'realized_pnl': round(pnl, 0),
        'result': result,
        'exit_reason': data.get('exit_reason', ''),
        'cumulative_pnl': round(cumulative_pnl, 0)
    }, cumulative_pnl


def failed_trade_row(trade_date, reason, cumulative_pnl):
    """Create a CSV row for a failed/skipped trade day."""
    try:
        day_name = datetime.strptime(trade_date, '%Y-%m-%d').strftime('%A')
    except:
        day_name = ''
    
    return {
        'date': trade_date,
        'day': day_name,
        'strategy': 'NO_TRADE',
        'spread_type': '',
        'atm_strike': '',
        'otm_strike': '',
        'expiry': '',
        'gap_points': '',
        'gap_percent': '',
        'entry_price': '',
        'entry_atm_price': '',
        'entry_otm_price': '',
        'exit_atm_price': '',
        'exit_otm_price': '',
        'credit_received': 0,
        'max_loss': 0,
        'realized_pnl': 0,
        'result': 'SKIP',
        'exit_reason': reason,
        'cumulative_pnl': round(cumulative_pnl, 0)
    }, cumulative_pnl


def rebuild_csv():
    """Rebuild entire CSV from trade history JSON files."""
    files = sorted(glob.glob(str(HISTORY_DIR / '*.json')))
    
    cumulative_pnl = 0
    rows = []
    
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
            row, cumulative_pnl = trade_json_to_row(data, cumulative_pnl)
            rows.append(row)
        except Exception as e:
            print(f"Error reading {f}: {e}")
    
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"CSV rebuilt: {len(rows)} trades written to {CSV_FILE}")
    print(f"Cumulative P&L: {cumulative_pnl:+,.0f}")
    return cumulative_pnl


def append_trade(trade_data):
    """Append a single trade to the CSV file."""
    # Get current cumulative P&L from last row
    cumulative_pnl = 0
    if CSV_FILE.exists():
        with open(CSV_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cumulative_pnl = float(row.get('cumulative_pnl', 0))
                except:
                    pass
    
    row, cumulative_pnl = trade_json_to_row(trade_data, cumulative_pnl)
    
    file_exists = CSV_FILE.exists()
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    
    return cumulative_pnl


def append_failed(trade_date, reason):
    """Append a failed/skipped day to the CSV file."""
    cumulative_pnl = 0
    if CSV_FILE.exists():
        with open(CSV_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cumulative_pnl = float(row.get('cumulative_pnl', 0))
                except:
                    pass
    
    row, cumulative_pnl = failed_trade_row(trade_date, reason, cumulative_pnl)
    
    file_exists = CSV_FILE.exists()
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    
    return cumulative_pnl


if __name__ == '__main__':
    rebuild_csv()
