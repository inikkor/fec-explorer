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

def fetch_schedule_b(session, api_key, committee_id, min_date=None):
    """Fetches Direct Contributions (Schedule B)"""
    records = []
    page = 1
    base_url = "https://api.open.fec.gov/v1/schedules/schedule_b/"
    
    params = {
        "api_key": api_key,
        "committee_id": committee_id,
        "two_year_transaction_period": 2026, # Locks it to the current cycle
        "per_page": 100,
    }
    if min_date: params["min_date"] = min_date

    print(f"  -> Fetching Direct Disbursements (Schedule B)...", flush=True)
    while True:
        try:
            params["page"] = page
            response = session.get(base_url, params=params, timeout=(5, 20))
            response.raise_for_status()
            
            payload = response.json()
            results = payload.get("results", [])
            
            if not results: break
                
            for record in results:
                records.append({
                    "transaction_id": record.get("transaction_id"),
                    "committee_id": record.get("committee_id"),
                    "disbursement_amount": record.get("disbursement_amount"),
                    "disbursement_date": record.get("disbursement_date"),
                    "recipient_name": record.get("recipient_name") or record.get("recipient_committee_name"),
                    # Explicitly grab IDs for the frontend matcher
                    "candidate_id": record.get("candidate_id"),
                    "beneficiary_candidate_id": record.get("beneficiary_candidate_id"),
                    "recipient_committee_id": record.get("recipient_committee_id"),
                    "record_type": "Direct"
                })
            
            if page >= payload.get("pagination", {}).get("pages", 1): break
            page += 1
            time.sleep(0.5)
            
        except Exception as e:
            print(f"     Error on Page {page}: {e}", flush=True)
            break
            
    return records

def fetch_schedule_e(session, api_key, committee_id, min_date=None):
    """Fetches Super PAC Independent Expenditures (Schedule E)"""
    records = []
    page = 1
    base_url = "https://api.open.fec.gov/v1/schedules/schedule_e/"
    
    params = {
        "api_key": api_key,
        "committee_id": committee_id,
        "cycle": 2026, # Schedule E uses 'cycle' instead of two_year_transaction_period
        "per_page": 100,
    }
    if min_date: params["min_date"] = min_date

    print(f"  -> Fetching Independent Expenditures (Schedule E)...", flush=True)
    while True:
        try:
            params["page"] = page
            response = session.get(base_url, params=params, timeout=(5, 20))
            response.raise_for_status()
            
            payload = response.json()
            results = payload.get("results", [])
            
            if not results: break
                
            for record in results:
                support_oppose = "SUPPORTING" if record.get("support_oppose_indicator") == "S" else "OPPOSING"
                target_candidate = record.get("candidate_name", "Unknown")
                
                records.append({
                    "transaction_id": record.get("transaction_id") or record.get("sub_id"),
                    "committee_id": record.get("committee_id"),
                    # Harmonize the keys so the frontend JS doesn't need to change!
                    "disbursement_amount": record.get("expenditure_amount"), 
                    "disbursement_date": record.get("expenditure_date"),
                    "recipient_name": f"{record.get('payee_name', 'Ad Agency')} (IE: {support_oppose} {target_candidate})",
                    "candidate_id": record.get("candidate_id"),
                    "record_type": "Super PAC Ad/Mailer"
                })
            
            if page >= payload.get("pagination", {}).get("pages", 1): break
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
    min_date = None

    if args.mode == "incremental":
        min_date = get_latest_date_from_file("fec_data.json")
        try:
            with open("fec_data.json", "r") as f:
                existing_data = json.load(f)
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

    # Merge Data
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

    # Save Output
    try:
        with open("fec_data.json", "w") as f:
            # Using standard formatting to ensure frontend parser compatibility
            json.dump(master_records, f, indent=2) 
        print(f"\nSuccessfully saved {len(master_records)} total items to fec_data.json", flush=True)
    except Exception as e:
        print(f"Critical error writing file: {e}", flush=True)

    print("--- Pipeline Finished ---", flush=True)

if __name__ == "__main__":
    main()
