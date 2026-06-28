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

# We can now use a list of keywords!
KEYWORDS_TO_CHECK = ["gaming laptops"] 
TARGET_DOMAIN = "dell.com"  # Change this to the website you want to track

# =====================================================================
# EXTRACTION FUNCTION (Volume + Rank)
# =====================================================================
def get_seo_data(page, keyword, target_domain):
    """
    Takes an already logged-in browser page, navigates to the keyword overview,
    and extracts both Search Volume and Domain Rank in one go.
    """
    print(f"\n--- Fetching full SEO profile for: '{keyword}' ---")
    encoded_kw = urllib.parse.quote_plus(keyword)
    target_url = f"https://www.semrush.com/analytics/keywordoverview/?q={encoded_kw}&db=in&currency=inr"
    
    try:
        page.goto(target_url, wait_until="load")
        
        # 1. GET SEARCH VOLUME
        print("Extracting Search Volume...")
        page.wait_for_selector("span.kwo-widget-total", timeout=20000)
        time.sleep(2)
        
        soup = BeautifulSoup(page.content(), "html.parser")
        volume_span = soup.find("span", class_="kwo-widget-total")
        volume = volume_span.text.strip() if volume_span else "N/A"
        
        # 2. GET RANK
        print(f"Extracting Rank for {target_domain}...")
        page.evaluate("window.scrollBy(0, 1500)") # Scroll down to load SERP table
        time.sleep(3) 
        
        rank = "Not found in top results"
        try:
            page.wait_for_selector("a.serp-item__link", timeout=10000)
            soup = BeautifulSoup(page.content(), "html.parser")
            serp_links = soup.find_all("a", class_="serp-item__link")
            
            for index, link in enumerate(serp_links, start=1):
                url = link.get('href', '')
                if target_domain in url:
                    rank = f"Rank #{index} (URL: {url})"
                    break
        except Exception as e:
            rank = "SERP Table failed to load"

        return {
            "keyword": keyword,
            "search_volume": volume,
            "rank": rank,
            "status": "Success"
        }

    except Exception as e:
        return {
            "keyword": keyword,
            "search_volume": None,
            "rank": None,
            "status": f"Automation Failed: {str(e)}"
        }

# =====================================================================
# MAIN EXECUTION (Login + Loop)
# =====================================================================
if __name__ == "__main__":
    print("=========================================")
    print("      SEMRUSH SCRAPER TEST RUN           ")
    print("=========================================\n")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()

        try:
            # --- STEP 1: LOGIN ONLY ONCE ---
            print("Navigating to Semrush Login...")
            page.goto("https://www.semrush.com/login/", wait_until="domcontentloaded")
            time.sleep(2)
            
            print("Checking for cookie pop-ups...")
            try:
                cookie_button = page.locator('button:has-text("Deny all"), button:has-text("Allow all cookies")').first
                cookie_button.wait_for(state="visible", timeout=3000)
                cookie_button.click()
                print("Cookie banner dismissed!")
                time.sleep(1)
            except Exception:
                print("No cookie banner appeared. Moving on...")

            print("Entering credentials...")
            page.wait_for_selector('input[type="email"]', timeout=15000)
            page.type('input[type="email"]', email, delay=10)
            time.sleep(0.5)
            page.type('input[type="password"]', password, delay=10)
            time.sleep(0.5)
            page.click('button[type="submit"]')

            print("Waiting for dashboard redirect...")
            page.wait_for_url("**/home/**", timeout=30000)
            time.sleep(2) 

            # --- STEP 2: LOOP THROUGH KEYWORDS ---
            for kw in KEYWORDS_TO_CHECK:
                data = get_seo_data(page, kw, TARGET_DOMAIN)
                results.append(data)
                
                # IMPORTANT: Pause between keywords if you add more to the list
                time.sleep(5) 

        except Exception as e:
            print(f"Critial Pipeline Error: {e}")
        
        finally:
            print("\nClosing browser...")
            browser.close()

    print("\n=========================================")
    print("             FINAL RESULT                ")
    print("=========================================")
    for res in results:
        print(res)