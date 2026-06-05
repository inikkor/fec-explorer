import json
import urllib.request
import os

# We can use the ProPublica API (Free) or a simple public CSV URL.
# For simplicity, here is the structure that will update your members.json
def get_rosters():
    # This URL is an example; you can swap it for the official Clerk's raw data
    url = "https://theunitedstates.io/congress-legislators/legislators-current.json"
    
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read())
        
    members = []
    for m in data:
        # Filter for current members
        if m.get('terms') and m['terms'][-1].get('end') >= '2026-01-01':
            last_term = m['terms'][-1]
            members.append({
                "name": f"{m['name']['first']} {m['name']['last']}",
                "chamber": last_term['type'],
                "state": last_term['state'],
                "party": last_term['party']
            })
            
    with open('members.json', 'w') as f:
        json.dump(members, f, indent=2)
    print(f"Successfully updated members.json with {len(members)} records.")

if __name__ == "__main__":
    get_rosters()
