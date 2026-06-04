import os
import json
import time
import urllib.request
import urllib.error

# Uses your secure API key stored in GitHub Secrets
API_KEY = os.environ.get('FEC_API_KEY')
if not API_KEY:
    print("Error: FEC_API_KEY environment variable not set.")
    exit(1)

BASE_URL = 'https://api.open.fec.gov/v1'
PAC_IDS = ['C00797670', 'C00799031', 'C00441949', 'C00710848', 'C00345132', 'C00697219', 'C00278143']

all_results = []

print("Starting FEC data extraction...")

for pac_id in PAC_IDS:
    page = 1
    print(f"Fetching data for PAC: {pac_id}")
    while True:
        url = f"{BASE_URL}/schedules/schedule_b/?api_key={API_KEY}&committee_id={pac_id}&two_year_transaction_period=2026&per_page=100&page={page}"
        req = urllib.request.Request(url)
        
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read())
                records = data.get('results', [])
                
                # Keep the JSON file size small by only saving fields the UI actually uses
                for r in records:
                    clean_record = {
                        "disbursement_date": r.get("disbursement_date"),
                        "disbursement_amount": r.get("disbursement_amount", 0),
                        "recipient_name": r.get("recipient_name"),
                        "recipient_committee_name": r.get("recipient_committee_name"),
                        "committee_id": r.get("committee_id"),
                        "candidate_id": r.get("candidate_id"),
                        "beneficiary_candidate_id": r.get("beneficiary_candidate_id"),
                        "recipient_committee_id": r.get("recipient_committee_id")
                    }
                    all_results.append(clean_record)
                
                pagination = data.get('pagination', {})
                if page >= pagination.get('pages', 1):
                    break
                page += 1
                time.sleep(0.5) # Be polite to the government servers
                
        except urllib.error.URLError as e:
            print(f"Failed to fetch {pac_id} on page {page}: {e}")
            break

# Save the master dataset
with open('fec_data.json', 'w') as f:
    json.dump(all_results, f)

print(f"Extraction complete! Saved {len(all_results)} total records.")
