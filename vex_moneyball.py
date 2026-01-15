import requests
import pandas as pd
import sys
import time

# ==============================================================================
#  VEX SCOUT: CLUTCH EDITION (Separate Leaderboards)
# ==============================================================================

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"
TARGET_SKU = "RE-V5RC-25-0179"
def get_push_back_id(api_key):
    """Automatically finds the Season ID for 'Push Back'"""
    print(f"[INFO] 0. Finding Season ID for 'Push Back'...")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    try:
        url = "https://www.robotevents.com/api/v2/seasons?program[]=1"
        r = requests.get(url, headers=headers)
        r.raise_for_status() # This checks for 401 (Bad Key) or 404 errors
        
        for season in r.json()['data']:
            if "Push Back" in season['name']:
                print(f"       ✅ Found Season: {season['name']} (ID: {season['id']})")
                return season['id']
        
        # Fallback
        print("       ⚠️ 'Push Back' not found by name. Defaulting to latest season.")
        return r.json()['data'][-1]['id']

    except Exception as e:
        # HERE IS THE FIX: We print the error specifically
        print(f"\n[CRITICAL ERROR] Could not connect to RobotEvents.")
        print(f"Error Details: {e}")
        if 'r' in locals() and r.status_code == 401:
            print("reason: UNAUTHORIZED. Please check your API_KEY.")
        sys.exit()

def get_true_history(sku, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    SEASON_ID = get_push_back_id(api_key)
    
    # --- PART 1: CONNECT ---
    print(f"\n[INFO] 1. Connecting to {sku}...")
    try:
        r = requests.get(f"https://www.robotevents.com/api/v2/events?sku={sku}&include=divisions", headers=headers)
        r.raise_for_status()
        event_data = r.json()['data'][0]
        event_id = event_data['id']
        divisions = event_data.get('divisions', [])
        print(f"       ✅ Connected to: {event_data['name']}")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return None
    
    stats = {}

    # --- PART 2: RANKINGS ---
    print(f"[INFO] 2. Downloading Rankings...")
    for div in divisions:
        page = 1
        while True:
            rank_url = f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/rankings?per_page=100&page={page}"
            try:
                r = requests.get(rank_url, headers=headers)
                data = r.json().get('data', [])
                if not data: break
                
                for t in data:
                    name = t['team']['name']
                    total = t['wins'] + t['losses'] + t['ties']
                    if total == 0: continue
                    stats[name] = {
                        "Team_ID": t['team']['id'], "Cur_Rank": t['rank'],
                        "Record": f"{t['wins']}-{t['losses']}-{t['ties']}",
                        "Cur_Auto": t['ap'] / total, "Cur_Skills": 0, "Past_Wins": 0
                    }
                page += 1
            except: break

    # --- PART 3: SKILLS ---
    print(f"[INFO] 3. Downloading Skills...")
    page = 1
    while True:
        r = requests.get(f"https://www.robotevents.com/api/v2/events/{event_id}/skills?per_page=100&page={page}", headers=headers)
        data = r.json().get('data', [])
        if not data: break
        for t in data:
            name = t['team']['name']
            if name in stats:
                stats[name]['Cur_Skills'] = max(stats[name]['Cur_Skills'], t['score'])
        page += 1

    # --- PART 4: HISTORY (Past Wins) ---
    print(f"[INFO] 4. Scanning 'Push Back' Awards...")
    count = 0
    for name, s in stats.items():
        count += 1
        sys.stdout.write(f"\rScanning {count}/{len(stats)}: {name}...")
        sys.stdout.flush()
        
        try:
            award_url = f"https://www.robotevents.com/api/v2/teams/{s['Team_ID']}/awards?season[]={SEASON_ID}"
            ar = requests.get(award_url, headers=headers)
            for a in ar.json().get('data', []):
                title = a['title']
                if "Champion" in title or "Excellence" in title or "Finalist" in title:
                    s['Past_Wins'] += 1
        except: pass 

    # --- PART 5: SCORING LOGIC ---
    print("\n[INFO] 5. Categorizing & Scoring...")
    final_list = []
    
    for name, s in stats.items():
        rank = s['Cur_Rank']
        wins = s['Past_Wins']
        
        # Base Score
        base_score = (s['Cur_Auto'] * 15) + s['Cur_Skills']
        
        # Logic Flags
        choke_penalty = 0
        clutch_bonus = 0
        status = "Solid"

        # 1. CHOKE RISK (High Rank, No Wins)
        if rank <= 8 and wins == 0:
            choke_penalty = -25
            status = "😨 CHOKE RISK"
        
        # 2. SLEEPER / CLUTCH (Mid Rank, Has Wins)
        if rank >= 10 and wins > 0:
            clutch_bonus = 40
            status = "🚀 SLEEPER"

        # 3. ELITE / GOD TIER overrides
        if s['Cur_Skills'] >= 90: 
            status = "GOD TIER"
        elif rank <= 5 and wins >= 2:
            status = "🏆 ELITE"

        # Win Bonus (Scaled)
        win_bonus = wins * 15 

        # Final Calc
        final_score = base_score + win_bonus + clutch_bonus + choke_penalty
        
        final_list.append({
            "Team": name,
            "Status": status,
            "Rank": rank,
            "Record": s['Record'],
            "Skills": s['Cur_Skills'],
            "Wins": wins,
            "Score": round(final_score, 1)
        })

    return pd.DataFrame(final_list)

# --- EXECUTION ---
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    df = get_true_history(TARGET_SKU, API_KEY)
    
    if df is not None and not df.empty:
        # 1. MASTER LIST (Top 15 by Score)
        print("\n" + "▓"*80)
        print("🏆 MASTER SCOUTING REPORT (Top 15 Overall)")
        print("▓"*80)
        master = df.sort_values(by='Score', ascending=False).head(15)
        print(master[['Team', 'Status', 'Rank', 'Wins', 'Skills', 'Score']].to_string(index=False))

        # 2. FRAUD WATCH
        print("\n" + "="*80)
        print("😨 FRAUD WATCH (Top 10 Rank but NO Wins)")
        print("   *High risk of losing early in elims*")
        print("="*80)
        frauds = df[(df['Rank'] <= 10) & (df['Wins'] == 0)].sort_values(by='Rank')
        if not frauds.empty:
            print(frauds[['Team', 'Rank', 'Record', 'Skills', 'Wins']].to_string(index=False))
        else:
            print("No frauds detected! Top 10 are solid.")

        # 3. SLEEPERS
        print("\n" + "="*80)
        print("🚀 SLEEPERS (Rank 10+ but HAVE Wins)")
        print("   *Draft these teams. They show up in finals.*")
        print("="*80)
        sleepers = df[(df['Rank'] >= 10) & (df['Wins'] > 0)].sort_values(by='Score', ascending=False)
        if not sleepers.empty:
            print(sleepers[['Team', 'Status', 'Rank', 'Wins', 'Skills']].to_string(index=False))
        else:
            print("No sleepers found.")

        # 4. SKILLS GIANTS
        print("\n" + "="*80)
        print("🤖 SKILLS GIANTS (Raw Skills Output)")
        print("="*80)
        skills = df.sort_values(by='Skills', ascending=False).head(10)
        print(skills[['Team', 'Skills', 'Rank', 'Wins']].to_string(index=False))