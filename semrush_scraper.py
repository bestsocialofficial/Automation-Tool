import time
import urllib.parse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv

# =====================================================================
# CONFIGURATION
# =====================================================================
load_dotenv()
email = os.getenv("SEMRUSH_EMAIL")
password = os.getenv("SEMRUSH_PASSWORD")
KEYWORD_TO_CHECK = "gaming laptops"


def scrape_semrush_metric(keyword, email, password):
    """
    Automates a Chromium browser with stealth parameters to log into Semrush
    and pull search volumes without triggering instant firewall closures.
    """
    print(f"Starting Semrush browser automation for '{keyword}'...")

    with sync_playwright() as p:
        # Launch with anti-bot detection arguments
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # --- STEP 1: NAVIGATE & LOGIN ---
            print("Navigating to Semrush Login...")
            page.goto("https://www.semrush.com/login/", wait_until="domcontentloaded")
            time.sleep(2)
            
            # --- HANDLE THE COOKIE BANNER ---
            print("Checking for cookie pop-ups...")
            try:
                cookie_button = page.locator('button:has-text("Deny all"), button:has-text("Allow all cookies")').first
                cookie_button.wait_for(state="visible", timeout=3000)
                cookie_button.click()
                print("Cookie banner dismissed!")
                time.sleep(1)
            except Exception:
                print("No cookie banner appeared. Moving on...")

           # --- FILL IN CREDENTIALS ---
            print("Waiting for login inputs...")
            page.wait_for_selector('input[type="email"]', timeout=15000)

            print("Entering credentials with a human-like delay...")
           
            page.type('input[type="email"]', email, delay=10)
            time.sleep(0.5)
            page.type('input[type="password"]', password, delay=10)
            time.sleep(0.5)
            
            print("Submitting login form...")
            page.click('button[type="submit"]')

            # Wait for the post-login dashboard redirect to finish settling
            print("Waiting for Semrush to finish internal redirects...")
            # Explicitly wait until Semrush lands on the home dashboard to avoid race conditions
            page.wait_for_url("**/home/**", timeout=30000)
            time.sleep(2) # Give the dashboard a brief moment to render 

            # --- STEP 2: NAVIGATION ---
            print(f"Navigating to Keyword Overview for: {keyword}")
            encoded_kw = urllib.parse.quote_plus(keyword)
            target_url = f"https://www.semrush.com/analytics/keywordoverview/?q={encoded_kw}&db=in"
            page.goto(target_url, wait_until="load")

            # --- STEP 3: WAIT FOR DATA TO RENDER ---
            print("Waiting for metrics to render on page...")
            
            page.wait_for_selector("span.kwo-widget-total", timeout=25000)
            time.sleep(2)

            # --- STEP 4: PARSE WITH BEAUTIFULSOUP ---
            raw_html = page.content()
            browser.close()

            print("Extracting target data elements...")
            soup = BeautifulSoup(raw_html, "html.parser")
            
            volume_span = soup.find("span", class_="kwo-widget-total")

            if volume_span:
                search_volume = volume_span.text.strip()
                return {
                    "keyword": keyword,
                    "search_volume": search_volume,
                    "status": "Success",
                }
            else:
                return {
                    "keyword": keyword,
                    "search_volume": None,
                    "status": "Structure Mismatch (Element not found)",
                }

        except Exception as e:
            if "browser" in locals():
                browser.close()
            return {
                "keyword": keyword,
                "search_volume": None,
                "status": f"Automation Failed: {str(e)}",
            }


if __name__ == "__main__":
    print("=========================================")
    print("      SEMRUSH SCRAPER TEST RUN           ")
    print("=========================================\n")

    result = scrape_semrush_metric(
        KEYWORD_TO_CHECK, email, password
    )

    print("\n=========================================")
    print("             FINAL RESULT                ")
    print("=========================================")
    print(result)