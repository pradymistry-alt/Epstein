import requests
import json

# --- DIAGNOSTIC TOOL ---
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"
# -----------------------

def run_diagnostic():
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    
    print("\n[TEST 1] Checking API Key permissions...")
    me_url = "https://www.robotevents.com/api/v2/me"
    r = requests.get(me_url, headers=headers)
    
    if r.status_code == 200:
        print("✅ API Key is GOOD.")
    elif r.status_code == 401:
        print("❌ API Key is INVALID (Access Denied). Check your copy-paste.")
        return
    else:
        print(f"⚠️ API Status: {r.status_code}")

    print("\n[TEST 2] Looking up Team 43440X (The 'Control' Subject)...")
    # We search for this specific team because we know they are at your event
    search_url = "https://www.robotevents.com/api/v2/teams?number=43440X"
    r = requests.get(search_url, headers=headers)
    
    if not r.json().get('data'):
        print("❌ Could not find the team. System check failed.")
        return
    
    team_data = r.json()['data'][0]
    team_id = team_data['id']
    print(f"✅ Found Team 43440X (ID: {team_id})")

    print("\n[TEST 3] Fetching Skills History for 43440X...")
    skills_url = f"https://www.robotevents.com/api/v2/teams/{team_id}/skills"
    r = requests.get(skills_url, headers=headers)
    
    print(f"HTTP Status Code: {r.status_code}")
    
    if r.status_code == 429:
        print("🔴 YOU ARE RATE LIMITED (The Penalty Box).")
        print("   * You ran the script too many times too fast.")
        print("   * FIX: Wait exactly 15 minutes, then try again.")
        return

    data = r.json().get('data', [])
    print(f"Number of Skills Entries Found: {len(data)}")
    
    if len(data) > 0:
        print("\n✅ SUCCESS! Here is the first entry found:")
        print(json.dumps(data[0], indent=2))
    else:
        print("\n⚠️ DATA IS EMPTY.")
        print("   * This means the team exists, but RobotEvents says they have ZERO history.")

if __name__ == "__main__":
    run_diagnostic()