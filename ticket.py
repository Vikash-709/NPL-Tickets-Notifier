import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ---------------- CONFIG ----------------
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1446061214580080745/egVAaF09D5SOb9s_4RURs3ko5Y_a9Jm2FI6z4S6bFIk2z7xGZvuxUpbxcMYp_yO2p0A5"
CHECK_URL = "https://events.khalti.com/events/ET25AMY4AUYM?sub_event=true"
POLL_INTERVAL = 45  # seconds (don't set too low to avoid being blocked)

# TEST MODE - Set to True to include Dec 7 match for testing
TEST_MODE = True  # Change to False after confirming it works

# Email config (optional - fill in if you want email notifications)
EMAIL_ENABLED = False
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "your_app_password"  # Use Gmail app password
RECIPIENT_EMAIL = "your_email@gmail.com"

# Matches to monitor
MATCHES = {
    "Qualifier 1": {"date": "Tue, 09 Dec", "keywords": ["qualifier 1", "q1"]},
    "Eliminator": {"date": "Wed, 10 Dec", "keywords": ["eliminator"]},
    "Qualifier 2": {"date": "Thu, 11 Dec", "keywords": ["qualifier 2", "q2"]},
    "Finals": {"date": "Sat, 13 Dec", "keywords": ["final", "finals"]},
}

# Add test match if in test mode
if TEST_MODE:
    MATCHES["Test Match (Dec 7)"] = {"date": "Sun, 07 Dec", "keywords": ["janakpur", "karnali", "yaks", "bolts"]}

notified_matches = set()
# ----------------------------------------


def send_discord_notification(message: str, match_name: str):
    """Send notification to Discord"""
    embed = {
        "content": f"🚨 **NPL TICKET ALERT** 🚨",
        "embeds": [{
            "title": "🎟️ Tickets Available!",
            "description": message,
            "color": 3447003,  # Blue color
            "fields": [
                {"name": "Match", "value": match_name, "inline": True},
                {"name": "Link", "value": f"[Buy Now]({CHECK_URL})", "inline": True}
            ],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK, json=embed, timeout=10)
        if response.status_code in (200, 204):
            print(f"✅ Discord notification sent for {match_name}")
            return True
        else:
            print(f"❌ Discord failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Discord error: {e}")
        return False


def send_email_notification(message: str, match_name: str):
    """Send email notification (backup)"""
    if not EMAIL_ENABLED:
        return
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = f"🎟️ NPL Tickets Available - {match_name}"
        
        body = f"""
        {message}
        
        Match: {match_name}
        Link: {CHECK_URL}
        
        Act fast - tickets sell out quickly!
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Email notification sent for {match_name}")
    except Exception as e:
        print(f"❌ Email error: {e}")


def setup_driver():
    """Setup headless Chrome driver"""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    driver = webdriver.Chrome(options=options)
    return driver


def check_tickets_selenium():
    """Check ticket availability using Selenium"""
    driver = None
    available_matches = []
    
    try:
        driver = setup_driver()
        print(f"   Loading page...")
        driver.get(CHECK_URL)
        
        # Wait for content to load (adjust selector based on actual page)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Give extra time for dynamic content
        time.sleep(3)
        
        # Get page source and look for indicators
        page_text = driver.page_source.lower()
        
        # DEBUGGING: Save page source if in test mode
        if TEST_MODE:
            with open("khalti_page_debug.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"   💾 Page source saved to khalti_page_debug.html for inspection")
        
        # Look for each match
        for match_name, match_info in MATCHES.items():
            date = match_info["date"].lower()
            keywords = match_info["keywords"]
            
            print(f"   Checking: {match_name} ({match_info['date']})")
            
            # Check if date is mentioned
            if date in page_text:
                print(f"      ✓ Date found")
                
                # Look for keywords
                context_found = False
                for keyword in keywords:
                    if keyword in page_text:
                        context_found = True
                        print(f"      ✓ Keyword found: '{keyword}'")
                        break
                
                if context_found:
                    # Extract context around the date (500 chars before and after)
                    date_pos = page_text.find(date)
                    context = page_text[max(0, date_pos-500):date_pos+500]
                    
                    # Check if it's sold out
                    is_sold_out = "sold out" in context or "soldout" in context
                    
                    # Check for availability indicators
                    has_buy_option = any(indicator in page_text for indicator in [
                        "buy now", "get ticket", "purchase", "book now", "add to cart", "available"
                    ])
                    
                    print(f"      Sold out: {is_sold_out}, Has buy option: {has_buy_option}")
                    
                    if not is_sold_out and has_buy_option:
                        available_matches.append(match_name)
                        print(f"      ✅ AVAILABLE!")
                    elif is_sold_out:
                        print(f"      ❌ Sold out")
                    else:
                        print(f"      ⚠️  Status unclear")
                else:
                    print(f"      ❌ Keywords not found")
            else:
                print(f"      ❌ Date not found on page")
        
        return available_matches
        
    except Exception as e:
        print(f"❌ Selenium error: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if driver:
            driver.quit()


def start_monitoring():
    """Main monitoring loop"""
    print("🚀 NPL Ticket Monitor Started")
    print(f"📍 Monitoring: {CHECK_URL}")
    print(f"⏰ Check interval: {POLL_INTERVAL} seconds")
    print(f"🎯 Watching for: {', '.join(MATCHES.keys())}")
    if TEST_MODE:
        print("⚠️  TEST MODE ENABLED - Includes Dec 7 match for testing")
    print("-" * 50)
    
    consecutive_errors = 0
    max_errors = 5
    
    while True:
        try:
            print(f"\n🔍 Checking... [{time.strftime('%H:%M:%S')}]")
            
            available_matches = check_tickets_selenium()
            
            if available_matches:
                print(f"\n🎉 Found {len(available_matches)} available match(es)!")
                for match_name in available_matches:
                    if match_name not in notified_matches:
                        match_info = MATCHES[match_name]
                        message = f"🎟️ Tickets for {match_name} ({match_info['date']}) are NOW AVAILABLE!"
                        
                        # Send notifications
                        discord_sent = send_discord_notification(message, match_name)
                        send_email_notification(message, match_name)
                        
                        if discord_sent:
                            notified_matches.add(match_name)
                        
                        # Alert sound (optional - works on some systems)
                        print("\a" * 3)  # Beep
                    else:
                        print(f"ℹ️  {match_name} - Already notified")
            else:
                print("⏳ No tickets available yet")
            
            consecutive_errors = 0
            
            if TEST_MODE:
                print("\n✅ Test run complete! Check your Discord for notification.")
                print("💡 Tip: Look at khalti_page_debug.html to see what the page contains")
                print("💡 If you got a notification, set TEST_MODE = False and run again!")
                break
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
            break
        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Error: {e}")
            
            if consecutive_errors >= max_errors:
                error_msg = f"⚠️ Monitor crashed after {max_errors} consecutive errors. Please check!"
                send_discord_notification(error_msg, "System Error")
                break
        
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # Quick check if dependencies are installed
    try:
        from selenium import webdriver
        print("✅ Selenium installed")
    except ImportError:
        print("❌ Please install: pip install selenium")
        print("❌ Also need ChromeDriver: https://chromedriver.chromium.org/")
        exit(1)
    
    start_monitoring()