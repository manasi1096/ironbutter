#!/usr/bin/env python3
"""
Automated Kite Login Script
============================
Runs daily at 8:30 AM IST via cron to refresh the Kite access token.

Usage:
    python3 auto_login.py

Cron entry (8:30 AM IST = 3:00 AM UTC):
    0 3 * * 1-5 /usr/bin/python3 /home/ubuntu/scripts/auto_login.py >> /var/log/openalgo/auto_login.log 2>&1
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
log_dir = Path('/var/log/openalgo')
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'auto_login.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
env_path = Path('/home/ubuntu/scripts/.env')
load_dotenv(env_path)

# Configuration
KITE_USER_ID = os.getenv('KITE_USER_ID')
KITE_PASSWORD = os.getenv('KITE_PASSWORD')
TOTP_SECRET = os.getenv('TOTP_SECRET')
KITE_API_KEY = os.getenv('KITE_API_KEY')
KITE_API_SECRET = os.getenv('KITE_API_SECRET')
OPENALGO_API_KEY = os.getenv('OPENALGO_API_KEY')
HOST_URL = os.getenv('HOST_URL', 'http://localhost:5000')

# Import Telegram notifier
try:
    from telegram_notifier import notify_login_success, notify_login_failed, notify_error
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("Telegram notifier not available")


def validate_config():
    """Validate that all required environment variables are set."""
    required = ['KITE_USER_ID', 'KITE_PASSWORD', 'TOTP_SECRET', 'KITE_API_KEY', 'KITE_API_SECRET']
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        return False
    return True


def generate_totp():
    """Generate current TOTP code using the secret."""
    import pyotp
    totp = pyotp.TOTP(TOTP_SECRET)
    code = totp.now()
    logger.info(f"Generated TOTP code: {code[:2]}****")
    return code


def auto_login_playwright():
    """
    Perform automated Kite login using Playwright.
    Returns the request_token on success.
    """
    from playwright.sync_api import sync_playwright
    
    logger.info("=" * 60)
    logger.info(f"Starting auto-login at {datetime.now()}")
    logger.info("=" * 60)
    
    # Variable to capture the redirect URL
    captured_request_token = [None]  # Using list to allow modification in nested function
    
    def handle_request(request):
        """Capture request URLs that contain request_token"""
        url = request.url
        if 'request_token=' in url:
            token = url.split('request_token=')[1].split('&')[0]
            logger.info(f"Captured request_token from request: {token[:10]}...")
            captured_request_token[0] = token
    
    def handle_response(response):
        """Capture redirect URLs that contain request_token"""
        url = response.url
        if 'request_token=' in url:
            token = url.split('request_token=')[1].split('&')[0]
            logger.info(f"Captured request_token from response: {token[:10]}...")
            captured_request_token[0] = token
    
    with sync_playwright() as p:
        # Launch browser in headless mode
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # Listen for requests and responses to capture redirect URL
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        try:
            # Step 1: Navigate to Kite login
            login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={KITE_API_KEY}"
            logger.info(f"Navigating to login URL...")
            page.goto(login_url, timeout=30000)
            time.sleep(2)
            
            # Step 2: Enter User ID
            logger.info(f"Entering user ID: {KITE_USER_ID[:2]}****")
            page.fill('input#userid', KITE_USER_ID)
            
            # Step 3: Enter Password
            logger.info("Entering password...")
            page.fill('input#password', KITE_PASSWORD)
            
            # Step 4: Click Submit
            logger.info("Submitting credentials...")
            page.click('button[type="submit"]')
            time.sleep(3)
            
            # Step 5: Enter TOTP
            logger.info("Waiting for TOTP page...")
            time.sleep(3)  # Give page time to load
            
            totp_code = generate_totp()
            logger.info(f"Generated TOTP: {totp_code}")
            
            # Try different possible selectors for TOTP input
            totp_selectors = [
                'input[type="number"]',
                'input[type="tel"]',
                'input[inputmode="numeric"]',
                'input[autocomplete="one-time-code"]',
                'input.totp',
                'input#totp',
                'input#userid',  # Sometimes reuses the same field
                'input[type="text"]',
                'input[placeholder*="OTP"]',
                'input[placeholder*="TOTP"]',
                'input[placeholder*="code"]',
            ]
            
            totp_filled = False
            for selector in totp_selectors:
                try:
                    locator = page.locator(selector)
                    if locator.count() > 0 and locator.first.is_visible():
                        logger.info(f"Found TOTP input with selector: {selector}")
                        locator.first.fill(totp_code)
                        totp_filled = True
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not totp_filled:
                # Last resort: try to find any visible input
                logger.warning("Standard selectors failed, trying to find any input...")
                all_inputs = page.locator('input:visible')
                if all_inputs.count() > 0:
                    logger.info(f"Found {all_inputs.count()} visible inputs, using first one")
                    all_inputs.first.fill(totp_code)
                    totp_filled = True
            
            if not totp_filled:
                logger.error("Could not find TOTP input field")
            
            # Step 6: Submit TOTP (sometimes auto-submits)
            time.sleep(2)
            try:
                submit_btn = page.locator('button[type="submit"]')
                if submit_btn.count() > 0 and submit_btn.first.is_visible():
                    logger.info("Clicking TOTP submit button...")
                    submit_btn.first.click()
            except Exception as e:
                logger.debug(f"No TOTP submit button or auto-submitted: {e}")
            
            time.sleep(3)
            
            # Step 7: Handle Authorization page (Kite Connect requires user to authorize the app)
            current_url = page.url
            logger.info(f"URL after TOTP: {current_url[:60]}...")
            
            if 'authorize' in current_url.lower():
                logger.info("On authorization page, looking for Authorize button...")
                
                # Try different selectors for the authorize button
                auth_selectors = [
                    'button:has-text("Authorize")',
                    'input[type="submit"][value*="Authorize"]',
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'a:has-text("Authorize")',
                    '.button-blue',
                    '#authorize',
                ]
                
                auth_clicked = False
                for selector in auth_selectors:
                    try:
                        btn = page.locator(selector)
                        if btn.count() > 0 and btn.first.is_visible():
                            logger.info(f"Found authorize button with selector: {selector}")
                            btn.first.click()
                            auth_clicked = True
                            break
                    except Exception as e:
                        continue
                
                if not auth_clicked:
                    logger.warning("Could not find Authorize button, trying any visible button...")
                    buttons = page.locator('button:visible, input[type="submit"]:visible')
                    if buttons.count() > 0:
                        logger.info(f"Clicking first visible button")
                        buttons.first.click()
                
                time.sleep(3)
            
            # Step 8: Extract request token from URL or captured redirect
            current_url = page.url
            logger.info(f"Final URL: {current_url[:80]}...")
            
            # First check if we captured the token from a redirect
            if captured_request_token[0]:
                logger.info(f"Using captured request_token from redirect")
                return captured_request_token[0]
            
            # Then check the current URL
            if 'request_token=' in current_url:
                request_token = current_url.split('request_token=')[1].split('&')[0]
                logger.info(f"Successfully obtained request_token: {request_token[:10]}...")
                return request_token
            else:
                # Check if we're on an error page (this is expected if redirect URL is localhost)
                if 'chrome-error' in current_url.lower() or 'error' in current_url.lower():
                    if captured_request_token[0]:
                        return captured_request_token[0]
                    logger.error(f"Redirect happened but couldn't capture token. URL: {current_url}")
                else:
                    logger.error(f"Could not find request_token in URL: {current_url}")
                
                # Take screenshot for debugging
                screenshot_path = log_dir / f"login_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(screenshot_path))
                logger.info(f"Screenshot saved to: {screenshot_path}")
                
                return None
                
        except Exception as e:
            logger.error(f"Auto-login error: {str(e)}")
            
            # Take screenshot for debugging
            try:
                screenshot_path = log_dir / f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                page.screenshot(path=str(screenshot_path))
                logger.info(f"Error screenshot saved to: {screenshot_path}")
            except:
                pass
            
            return None
            
        finally:
            browser.close()


def generate_access_token(request_token):
    """
    Generate access token from request token using Kite API.
    """
    from kiteconnect import KiteConnect
    
    try:
        kite = KiteConnect(api_key=KITE_API_KEY)
        data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
        access_token = data['access_token']
        logger.info(f"Generated access_token: {access_token[:10]}...")
        return access_token
    except Exception as e:
        logger.error(f"Failed to generate access token: {str(e)}")
        return None


def update_openalgo_token(access_token):
    """
    Update OpenAlgo with the new access token.
    This may need to be adjusted based on OpenAlgo's actual API.
    """
    import requests
    
    try:
        # Method 1: Try OpenAlgo's token update API (if available)
        response = requests.post(
            f"{HOST_URL}/api/v1/updatetoken",
            json={"access_token": access_token},
            headers={"X-API-Key": OPENALGO_API_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info("Successfully updated OpenAlgo token via API")
            return True
        else:
            logger.warning(f"API update returned: {response.status_code} - {response.text}")
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not update via API: {str(e)}")
    
    # Method 2: Save token to a file for OpenAlgo to read
    token_file = Path('/home/ubuntu/openalgo/db/access_token.txt')
    try:
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(access_token)
        logger.info(f"Saved access token to: {token_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to save token to file: {str(e)}")
        return False


def save_token_to_env(access_token):
    """Save the access token to the scripts .env file."""
    env_file = Path('/home/ubuntu/scripts/.env')
    
    try:
        if env_file.exists():
            content = env_file.read_text()
            lines = content.split('\n')
            
            # Update or add KITE_ACCESS_TOKEN
            token_found = False
            for i, line in enumerate(lines):
                if line.startswith('KITE_ACCESS_TOKEN='):
                    lines[i] = f'KITE_ACCESS_TOKEN={access_token}'
                    token_found = True
                    break
            
            if not token_found:
                lines.append(f'KITE_ACCESS_TOKEN={access_token}')
            
            env_file.write_text('\n'.join(lines))
            logger.info("Updated KITE_ACCESS_TOKEN in .env file")
            return True
        else:
            logger.error(f".env file not found: {env_file}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to update .env file: {str(e)}")
        return False


def main():
    """Main function to orchestrate the auto-login process."""
    logger.info("=" * 60)
    logger.info("KITE AUTO-LOGIN SCRIPT")
    logger.info("=" * 60)
    
    # Validate configuration
    if not validate_config():
        error_msg = "Configuration validation failed"
        logger.error(f"{error_msg}. Exiting.")
        if TELEGRAM_AVAILABLE:
            try:
                notify_login_failed(error_msg)
            except:
                pass
        sys.exit(1)
    
    # Perform login
    request_token = auto_login_playwright()
    
    if not request_token:
        error_msg = "Failed to obtain request_token"
        logger.error(f"{error_msg}. Exiting.")
        if TELEGRAM_AVAILABLE:
            try:
                notify_login_failed(error_msg)
            except:
                pass
        sys.exit(1)
    
    # Generate access token
    access_token = generate_access_token(request_token)
    
    if not access_token:
        error_msg = "Failed to generate access_token"
        logger.error(f"{error_msg}. Exiting.")
        if TELEGRAM_AVAILABLE:
            try:
                notify_login_failed(error_msg)
            except:
                pass
        sys.exit(1)
    
    # Save token to .env for other scripts
    save_token_to_env(access_token)
    
    # Update OpenAlgo
    update_openalgo_token(access_token)
    
    logger.info("=" * 60)
    logger.info("AUTO-LOGIN COMPLETED SUCCESSFULLY")
    logger.info("=" * 60)
    
    # Send success notification
    if TELEGRAM_AVAILABLE:
        try:
            notify_login_success()
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")


if __name__ == "__main__":
    main()

