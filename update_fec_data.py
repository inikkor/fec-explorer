import os
import json
import time
import urllib.request
import sys

# Force unbuffered output so logs appear instantly
sys.stdout.reconfigure(line_buffering=True)

print("--- Pipeline Initializing ---", flush=True)

API_KEY = os.environ.get('FEC_API_KEY')
PAC_IDS = ['C00797670', 'C00799031', 'C00441949', 'C00710848', 'C00345132', 'C00697219', 'C00278143']

# The secret sauce: Browser-like headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

all_results = []

for pac_id in PAC_IDS:
    print(f"Starting PAC: {pac_id}", flush=True)
    page = 1
    while True:
        url = f"https://api.open.fec.gov/v1/schedules/schedule_b/?api_key={API_KEY}&committee_id={pac_id}&two_year_transaction_period=2026&per_page=100&page={page}"
        
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read())
                records = data.get('results', [])
                print(f"  Page {page} fetched {len(records)} records", flush=True)
                
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
                time.sleep(1.5)
                
        except Exception as e:
            print(f"  Error on PAC {pac_id}: {e}", flush=True)
            break

with open('fec_data.json', 'w') as f:
    json.dump(all_results, f)
print("--- Pipeline Finished ---", flush=True)
