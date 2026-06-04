import os
import json
import time
import urllib.request
import urllib.error

API_KEY = os.environ.get('FEC_API_KEY')
BASE_URL = 'https://api.open.fec.gov/v1'
PAC_IDS = ['C00797670', 'C00799031', 'C00441949', 'C00710848', 'C00345132', 'C00697219', 'C00278143']

all_results = []

print(f"--- Pipeline Starting at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

for pac_id in PAC_IDS:
    page = 1
    pac_total = 0
    print(f"[STATUS] Starting download for PAC: {pac_id}")
    
    while True:
        url = f"{BASE_URL}/schedules/schedule_b/?api_key={API_KEY}&committee_id={pac_id}&two_year_transaction_period=2026&per_page=100&page={page}"
        req = urllib.request.Request(url)
        
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read())
                records = data.get('results', [])
                
                # Progress logging
                count = len(records)
                pac_total += count
                print(f"  [PAGE {page}] Fetched {count} records...")
                
                for r in records:
                    all_results.append({
                        "disbursement_date": r.get("disbursement_date"),
                        "disbursement_amount": r.get("disbursement_amount", 0),
                        "recipient_name": r.get("recipient_name"),
                        "recipient_committee_name": r.get("recipient_committee_name"),
                        "committee_id": r.get("committee_id"),
                        "candidate_id": r.get("candidate_id"),
                        "beneficiary_candidate_id": r.get("beneficiary_candidate_id"),
                        "recipient_committee_id": r.get("recipient_committee_id")
                    })
                
                pagination = data.get('pagination', {})
                if page >= pagination.get('pages', 1):
                    break
                page += 1
                time.sleep(0.6) # Slightly longer pause to ensure API stability
                
        except urllib.error.URLError as e:
            print(f"  [ERROR] Failed at PAC {pac_id}, Page {page}: {e.reason}")
            break

    print(f"[SUCCESS] Finished {pac_id}. Total records captured: {pac_total}")

with open('fec_data.json', 'w') as f:
    json.dump(all_results, f)

print(f"--- Pipeline Complete. Total aggregate records: {len(all_results)} ---")
