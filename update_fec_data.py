import os
import json
import time
import urllib.request
import urllib.error
import sys
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Force all output to show immediately
def log(msg):
    print(msg, flush=True)

log("--- Pipeline Starting ---")

API_KEY = os.environ.get('FEC_API_KEY')
if not API_KEY:
    log("ERROR: API Key missing!")
    sys.exit(1)

print(f"DEBUG: API Key present: {bool(os.environ.get('FEC_API_KEY'))}", flush=True)

BASE_URL = 'https://api.open.fec.gov/v1'
PAC_IDS = ['C00797670', 'C00799031', 'C00441949', 'C00710848', 'C00345132', 'C00697219', 'C00278143']

all_results = []

for pac_id in PAC_IDS:
    page = 1
    log(f"Fetching PAC: {pac_id}")
    
    while True:
        url = f"{BASE_URL}/schedules/schedule_b/?api_key={API_KEY}&committee_id={pac_id}&two_year_transaction_period=2026&per_page=100&page={page}"
        log(f"  Requesting URL: {url}")
        
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                data = json.loads(response.read())
                records = data.get('results', [])
                log(f"  Page {page} returned {len(records)} records.")
                
                for r in records:
                    all_results.append({
                        "disbursement_date": r.get("disbursement_date"),
                        "disbursement_amount": r.get("disbursement_amount", 0),
                        "recipient_name": r.get("recipient_name"),
                        "committee_id": r.get("committee_id")
                    })
                
                if page >= data.get('pagination', {}).get('pages', 1):
                    break
                page += 1
                time.sleep(1) 
                
        except Exception as e:
            log(f"  ERROR on PAC {pac_id}: {e}")
            break

with open('fec_data.json', 'w') as f:
    json.dump(all_results, f)

log("--- Pipeline Finished ---")
