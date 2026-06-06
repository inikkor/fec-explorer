import os
import sys
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Ensure logs print immediately to GitHub Actions console
sys.stdout.reconfigure(line_buffering=True)

# List of PAC IDs extracted from your pipeline logs
PAC_LIST = [
    "C00797670",
    "C00799031",
    "C00441949",
    "C00710848",
    "C00345132",
    "C00697219",
    "C00278143"
]

def get_robust_session():
    """Configures a requests session with automatic retry logic for connection/server errors."""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # Retry up to 5 times before giving up
        backoff_factor=1,  # Wait 1s, 2s, 4s, 8s, 16s between retries
        status_forcelist=[429, 500, 502, 503, 504],  # Retry on rate limits or server drops
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def fetch_pac_data(session, api_key, committee_id):
    """Fetches all pages of Schedule B disbursements for a single PAC."""
    all_pac_records = []
    page = 1
    
    # OpenFEC API endpoint for disbursements
    base_url = "https://api.open.fec.gov/v1/schedules/schedule_b/"
    
    # Initial parameters
    params = {
        "api_key": api_key,
        "committee_id": committee_id,
        "per_page": 100,
        "page": page
    }

    while True:
        try:
            params["page"] = page
            # Set explicit timeouts: 5s to connect, 20s to read data chunks
            response = session.get(base_url, params=params, timeout=(5, 20))
            response.raise_for_status()
            
            payload = response.json()
            results = payload.get("results", [])
            fetched_count = len(results)
            
            print(f"  Page {page} fetched {fetched_count} records", flush=True)
            
            if not results:
                break
                
            # Process and clean the records to keep only the 4 required keys
            for record in results:
                all_pac_records.append({
                    "committee_id": record.get("committee_id"),
                    "disbursement_amount": record.get("disbursement_amount"),
                    "disbursement_date": record.get("disbursement_date"),
                    "recipient_name": record.get("recipient_name")
                })
            
            # Check pagination metadata to see if another page exists
            pagination = payload.get("pagination", {})
            total_pages = pagination.get("pages", 1)
            
            if page >= total_pages:
                break
                
            page += 1
            
            # Tiny polite delay to protect API rate limit limits
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  Error on PAC {committee_id} during Page {page}: {e}", flush=True)
            # Re-raise the exception to be handled at the pipeline level (skips to next PAC)
            raise e

    return all_pac_records

def main():
    print("--- Pipeline Initializing ---", flush=True)
    
    # Best practice: Fallback to DEMO_KEY if the repo secret isn't configured yet
    api_key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    if api_key == "DEMO_KEY":
        print("Warning: Using 'DEMO_KEY'. Rate limits will be heavily restricted.", flush=True)

    session = get_robust_session()
    master_records = []

    for pac in PAC_LIST:
        print(f"Starting PAC: {pac}", flush=True)
        try:
            pac_data = fetch_pac_data(session, api_key, pac)
            master_records.extend(pac_data)
        except Exception:
            print(f"Skipping rest of PAC {pac} due to persistent connection issues. Moving forward...", flush=True)
            continue

    # Write data cleanly back to the minified flat-file structure
    try:
        with open("fec_data.json", "w") as f:
            json.dump(master_records, f, separators=(',', ':'))
        print(f"Successfully saved {len(master_records)} items to fec_data.json", flush=True)
    except Exception as e:
        print(f"Critical error writing file: {e}", flush=True)

    print("--- Pipeline Finished ---", flush=True)

if __name__ == "__main__":
    main()
