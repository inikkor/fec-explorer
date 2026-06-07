import os
import sys
import json
import time
import argparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.stdout.reconfigure(line_buffering=True)

PAC_LIST = ["C00797670", "C00799031", "C00441949", "C00710848", "C00345132", "C00697219", "C00278143"]

def get_robust_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def get_latest_date_from_file(filename="fec_data.json"):
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            if not data:
                return None
            dates = [r.get("disbursement_date") for r in data if r.get("disbursement_date")]
            if dates:
                latest = max(dates)
                return latest.split("T")[0] 
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return None

def fetch_pac_data(session, api_key, committee_id, min_date=None):
    all_pac_records = []
    page = 1
    base_url = "https://api.open.fec.gov/v1/schedules/schedule_b/"
    
    params = {
        "api_key": api_key,
        "committee_id": committee_id,
        "per_page": 100,
        "page": page,
        "two_year_transaction_period": 2026  # <--- ADD THIS LINE

    }

    if min_date:
        params["min_date"] = min_date

    while True:
        try:
            params["page"] = page
            response = session.get(base_url, params=params, timeout=(5, 20))
            response.raise_for_status()
            
            payload = response.json()
            results = payload.get("results", [])
            print(f"  Page {page} fetched {len(results)} records", flush=True)
            
            if not results:
                break
                
            for record in results:
                all_pac_records.append({
                    "transaction_id": record.get("transaction_id"),
                    "committee_id": record.get("committee_id"),
                    "disbursement_amount": record.get("disbursement_amount"),
                    "disbursement_date": record.get("disbursement_date"),
                    "recipient_name": record.get("recipient_name")
                })
            
            pagination = payload.get("pagination", {})
            if page >= pagination.get("pages", 1):
                break
                
            page += 1
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  Error on PAC {committee_id} during Page {page}: {e}", flush=True)
            raise e

    return all_pac_records

def main():
    # 1. Setup Arguments
    parser = argparse.ArgumentParser(description="FEC Data Fetcher")
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental", 
                        help="Choose 'full' for complete historical refresh or 'incremental' for new records only.")
    args = parser.parse_args()
    
    print(f"--- Pipeline Initializing ({args.mode.upper()} MODE) ---", flush=True)
    api_key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    
    existing_data = []
    min_date = None

    # 2. Handle Incremental Logic
    if args.mode == "incremental":
        min_date = get_latest_date_from_file("fec_data.json")
        try:
            with open("fec_data.json", "r") as f:
                existing_data = json.load(f)
            print(f"Loaded {len(existing_data)} existing records. Fetching updates since: {min_date}", flush=True)
        except FileNotFoundError:
            print("No existing data file found. Falling back to full historical download.", flush=True)
            min_date = None
    else:
        print("Full mode selected. Ignoring local history and fetching all records.", flush=True)

    # 3. Fetch Data
    session = get_robust_session()
    new_records = []

    for pac in PAC_LIST:
        print(f"Starting PAC: {pac}", flush=True)
        try:
            pac_data = fetch_pac_data(session, api_key, pac, min_date)
            new_records.extend(pac_data)
        except Exception:
            print(f"Skipping rest of PAC {pac} due to errors.", flush=True)
            continue

    # 4. Merge Data (Only matters for incremental)
    if args.mode == "incremental":
        master_dict = {}
        for record in existing_data:
            key = record.get("transaction_id") or f"{record.get('committee_id')}-{record.get('disbursement_date')}-{record.get('disbursement_amount')}"
            master_dict[key] = record
            
        for record in new_records:
            key = record.get("transaction_id") or f"{record.get('committee_id')}-{record.get('disbursement_date')}-{record.get('disbursement_amount')}"
            master_dict[key] = record

        master_records = list(master_dict.values())
    else:
        # If full mode, master is just the newly downloaded records
        master_records = new_records

    # 5. Save Output (One JSON object per line)
    try:
        with open("fec_data.json", "w") as f:
            for record in master_records:
                # json.dumps converts the dict to a compact string, then we add a newline
                f.write(json.dumps(record, separators=(',', ':')) + "\n")
                
        print(f"Successfully saved {len(master_records)} total items to fec_data.json", flush=True)
    except Exception as e:
        print(f"Critical error writing file: {e}", flush=True)

    print("--- Pipeline Finished ---", flush=True)

if __name__ == "__main__":
    main()
