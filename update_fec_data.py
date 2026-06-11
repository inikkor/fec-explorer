import os
import sys
import json
import time
import argparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Ensure logs appear immediately in GitHub Actions
sys.stdout.reconfigure(line_buffering=True)

PAC_LIST = ["C00797670", "C00799031", "C00441949", "C00710848", "C00345132", "C00697219", "C00278143"]

def get_robust_session():
    """Sets up an HTTP session with automatic retries for rate limits and server errors."""
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
    """Reads the existing JSON file to find the most recent transaction date."""
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

def fetch_schedule_b(session, api_key, committee_id, min_date=None):
    """Fetches Direct Contributions (Schedule B)"""
    records = []
    base_url = "https://api.open.fec.gov/v1/schedules/schedule_b/"
    
    params = {
        "api_key": api_key,
        "committee_id": committee_id,
        "two_year_transaction_period": 2026, # Locks to current cycle to prevent massive historical pulls
        "per_page": 100,
    }
    if min_date: params["min_date"] = min_date

    print(f"  -> Fetching Direct Disbursements (Schedule B)...", flush=True)
    page = 1
    while True:
        try:
            response = session.get(base_url, params=params, timeout=(5, 20))
            response.raise_for_status()
            
            payload = response.json()
            results = payload.get("results", [])
            
            if not results: break
                
            for record in results:
                # Normalize date format
                raw_date = record.get("disbursement_date")
                formatted_date = raw_date if not raw_date or "T" in raw_date else f"{raw_date}T00:00:00"

                records.append({
                    "transaction_id": record.get("transaction_id"),
                    "committee_id": record.get("committee_id"),
                    "disbursement_amount": record.get("disbursement_amount") or 0.0,
                    "disbursement_date": formatted_date,
                    "recipient_name": record.get("recipient_name") or record.get("recipient_committee_name"),
                    "candidate_id": record.get("candidate_id"),
                    "beneficiary_candidate_id": record.get("beneficiary_candidate_id"),
                    "recipient_committee_id": record.get("recipient_committee_id"),
                    "record_type": "Direct Contribution"
                })
            
            pagination = payload.get("pagination", {})
            last_indexes = pagination.get("last_indexes")
            if not last_indexes:
                break
                
            params.update(last_indexes)
            page += 1
            time.sleep(0.5) # Be polite to the API
            
        except Exception as e:
            print(f"     Error on Page {page}: {e}", flush=True)
            break
            
    return records

def fetch_schedule_e(session, api_key, committee_id, min_date=None):
    """Fetches Super PAC Independent Expenditures (E) with strict key normalization"""
    records = []
    base_url = "https://api.open.fec.gov/v1/schedules/schedule_e/"
    
    params = {
        "api_key": api_key,
        "committee_id": committee_id,
        "cycle": 2026, # Schedule E uses 'cycle'
        "per_page": 100,
    }
    if min_date:
        params["min_expenditure_date"] = min_date


    print(f"  -> Fetching Independent Expenditures (Schedule E)...", flush=True)
    page = 1
    while True:
        try:
            response = session.get(base_url, params=params, timeout=(5, 20))
            response.raise_for_status()
            
            payload = response.json()
            results = payload.get("results", [])
            
            if not results: break
                
            for record in results:
                support_oppose = "SUPPORTING" if record.get("support_oppose_indicator") == "S" else "OPPOSING"
                target_candidate = record.get("candidate_name", "Unknown Candidate")
                
                # Normalize date to include the "T00:00:00" timestamp if missing
                raw_date = record.get("expenditure_date")
                formatted_date = None
                if raw_date:
                    formatted_date = raw_date if "T" in raw_date else f"{raw_date}T00:00:00"

                records.append({
                    "transaction_id": record.get("transaction_id") or record.get("sub_id"),
                    "committee_id": record.get("committee_id"),
                    "disbursement_amount": record.get("expenditure_amount") or 0.0, 
                    "disbursement_date": formatted_date,
                    "recipient_name": f"{record.get('payee_name', 'Ad Agency')} (IE: {support_oppose} {target_candidate})",
                    "candidate_id": record.get("candidate_id") or "",
                    # Explicitly pad missing keys with null/None to satisfy the frontend parser
                    "beneficiary_candidate_id": None,
                    "recipient_committee_id": None,
                    "record_type": "Super PAC IE"
                })
            
            pagination = payload.get("pagination", {})
            last_indexes = pagination.get("last_indexes")
            if not last_indexes:
                break
                
            params.update(last_indexes)
            page += 1
            time.sleep(0.5)
            
        except Exception as e:
            print(f"     Error on Page {page}: {e}", flush=True)
            break
            
    return records

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    args = parser.parse_args()
    
    print(f"--- Pipeline Initializing ({args.mode.upper()} MODE) ---", flush=True)
    api_key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    
    existing_data = []

# 1. Initialize min_date at the top level first
    min_date = None

    if args.mode == "incremental":
        try:
            # 2. Assign the date inside the try block
            min_date = get_latest_date_from_file("fec_data.json")
            
            with open("fec_data.json", "r") as f:
                existing_data = json.load(f)
                
            # 3. Print the debug statement here safely
            print(f"Loaded existing records. Fetching updates since: {min_date}", flush=True)
            
        except Exception:
            print("No valid existing data. Falling back to full historical download.", flush=True)
            min_date = None


    

    session = get_robust_session()
    new_records = []

    for pac in PAC_LIST:
        print(f"\nProcessing PAC: {pac}", flush=True)
        # Fetch BOTH schedules for every PAC
        new_records.extend(fetch_schedule_b(session, api_key, pac, min_date))
        new_records.extend(fetch_schedule_e(session, api_key, pac, min_date))

    # Merge Data using transaction IDs or fallback composites to prevent duplicates
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
        master_records = new_records

    # Save Output as standard JSON Array
    try:
        with open("fec_data.json", "w") as f:
            json.dump(master_records, f, indent=2) 
        print(f"\nSuccessfully saved {len(master_records)} total items to fec_data.json", flush=True)
    except Exception as e:
        print(f"Critical error writing file: {e}", flush=True)

    print("--- Pipeline Finished ---", flush=True)

if __name__ == "__main__":
    main()
