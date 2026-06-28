import os
import time
import requests
from dotenv import load_dotenv

# =====================================================================
# CONFIGURATION
# =====================================================================
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")

KEYWORDS_TO_CHECK = ["gaming laptops", "best running shoes", "data engineering roles"]
TARGET_DOMAIN = "amazon.in"

# =====================================================================
# SERPAPI EXTRACTION FUNCTION
# =====================================================================
def get_serpapi_data(keyword, target_domain, api_key):
    """
    Queries SerpApi for a Google Search, parses the structured JSON response,
    and determines the exact ranking position of the target domain.
    """
    print(f"\n--- Requesting SERP data for: '{keyword}' ---")
    
   
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": keyword,
        "gl": "in",
        "num": 100,
        "api_key": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return {
                "keyword": keyword,
                "rank": None,
                "status": f"API Error: Received status code {response.status_code}"
            }
            
        data = response.json()
        organic_results = data.get("organic_results", [])

        
        print(f"Top 5 competitors for '{keyword}':")
        for i in range(min(5, len(organic_results))):
            print(f"{i+1}. {organic_results[i].get('link')}")
        
        # Loop through the structured JSON results
        rank = "Not found in top 100 results"
        for result in organic_results:
            position = result.get("position")
            link = result.get("link", "")
            
            if target_domain in link:
                rank = f"Rank #{position} (URL: {link})"
                break
                
        return {
            "keyword": keyword,
            "rank": rank,
            "status": "Success"
        }
        
    except Exception as e:
        return {
            "keyword": keyword,
            "rank": None,
            "status": f"Pipeline Error: {str(e)}"
        }

# =====================================================================
# MAIN EXECUTION LOOP
# =====================================================================
if __name__ == "__main__":
    print("=========================================")
    print("      SERPAPI RANK TRACKER RUN           ")
    print("=========================================\n")
    
    if not SERPAPI_KEY:
        print("Error: SERPAPI_API_KEY not found in environment. Check your .env file.")
        exit(1)

    results = []
    
    # Process the list of keywords sequentially
    for kw in KEYWORDS_TO_CHECK:
        data = get_serpapi_data(kw, TARGET_DOMAIN, SERPAPI_KEY)
        results.append(data)
        print(f"Result: {data['rank']} | Status: {data['status']}")
        
        time.sleep(1)

    print("\n=========================================")
    print("             FINAL RESULT                ")
    print("=========================================")
    for res in results:
        print(res)