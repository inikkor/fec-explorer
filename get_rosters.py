import json
import urllib.request
import ssl
import sys

# Ensure logs appear immediately in GitHub Actions
sys.stdout.reconfigure(line_buffering=True)

# Bypass SSL certificate verification for this script
ssl._create_default_https_context = ssl._create_unverified_context

def get_rosters():
    # Correct direct link to the raw JSON file
    url = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/data/legislators-current.json"
    
    # Browser-like headers to bypass bot blocks
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print("Fetching roster from GitHub raw content...", flush=True)
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read())
            
        members = []
        for m in data:
            # Check if member has terms and filter for current status
            if m.get('terms'):
                last_term = m['terms'][-1]
                # Filter for those currently in office
                if last_term.get('end') >= '2026-01-01':
                    members.append({
                        "name": f"{m['name']['first']} {m['name']['last']}",
                        "chamber": last_term['type'],
                        "state": last_term['state'],
                        "party": last_term['party']
                    })
        
        with open('members.json', 'w') as f:
            json.dump(members, f, indent=2)
            
        print(f"Successfully updated members.json with {len(members)} records.", flush=True)
        
    except Exception as e:
        print(f"Error fetching roster: {e}", flush=True)

if __name__ == "__main__":
    get_rosters()
