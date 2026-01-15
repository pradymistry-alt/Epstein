import requests
import pandas as pd
import sys
import time
import json

# ==============================================================================
#  STEINTRACKER v6.1 (BRUTE FORCE DEBUG)
#  * Removes 'scored' check logic *
#  * Prints exactly why extraction fails *
# ==============================================================================

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"
MY_COMP_SKU = "RE-V5RC-25-9994" 

# --- THRESHOLDS ---
MIN_AVG_POINTS = 35.0   
MIN_SP_STRENGTH = 18.0  

def get_push_back_id(api_key):
    print(f"[INFO] 0. Finding Season ID for 'Push Back'...")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        url = "https://www.robotevents.com/api/v2/seasons?program[]=1"
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        for season in r.json()['data']:
            if "Push Back" in season['name'] or "High Stakes" in season['name']:
                print(f"       ✅ Found Season: {season['name']} (ID: {season['id']})")
                return season['id']
        return r.json()['data'][-1]['id']
    except Exception as e:
        print(f"[CRITICAL ERROR] Could not connect to RobotEvents: {e}")
        sys.exit()

def extract_from_list_format(alliance_list, debug=False):
    """
    Parses the List format seen in Spyglass:
    [ {color: 'blue', teams: [...]}, {color: 'red', teams: [...]} ]
    """
    r_score, r_ids = 0, []
    b_score, b_ids = 0, []
    
    found_red = False
    found_blue = False

    for a in alliance_list:
        color = a.get('color')
        score = a.get('score', 0)
        
        # Extract IDs
        ids = []
        if 'teams' in a:
            for t_item in a['teams']:
                # Spyglass format: { "team": { "id": 123 } }
                if 'team' in t_item and 'id' in t_item['team']:
                    ids.append(t_item['team']['id'])
                elif 'id' in t_item: # Fallback
                     ids.append(t_item['id'])
        
        if color == 'red':
            r_score = score
            r_ids = ids
            found_red = True
        elif color == 'blue':
            b_score = score
            b_ids = ids
            found_blue = True

    if debug and (not found_red or not found_blue):
        print(f"   [DEBUG FAIL] Missing Color? RedFound:{found_red} BlueFound:{found_blue}")

    return (r_score, r_ids), (b_score, b_ids)

def scan_my_comp(sku, api_key, season_id):
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    print(f"\n" + "⚡"*60)
    print(f"   PHASE 1: SCANNING EVENT & DOWNLOADING MATCHES")
    print("⚡"*60)
    
    try:
        r = requests.get(f"https://www.robotevents.com/api/v2/events?sku={sku}&include=divisions", headers=headers)
        r.raise_for_status()
        event_data = r.json()['data'][0]
        event_id = event_data['id']
        divisions = event_data.get('divisions', [])
        print(f"   ✅ Connected to: {event_data['name']}")
    except: return None

    stats = {}
    
    # 1. RANKINGS
    print(f"   [1/2] Analyzing Rankings (DNA)...")
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
                    t_id = t['team']['id']
                    total = t['wins']+t['losses']+t['ties']
                    if total == 0: continue
                    
                    stats[name] = {
                        "Team_ID": t_id, "Rank": t['rank'], 
                        "Auto": round(t['ap'] / total, 2), 
                        "WP": round(t['wp'] / total, 2), 
                        "SP": round(t['sp'] / total, 1),
                        "Scores": [], "Avg_Pts": 0
                    }
                page += 1
            except: break

    # 2. MATCH SCORES (BRUTE FORCE)
    print(f"   [2/2] Downloading Match Scores...")
    match_count = 0
    debug_prints = 0
    
    for div in divisions:
        page = 1
        while True:
            m_url = f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/matches?per_page=100&page={page}"
            try:
                r = requests.get(m_url, headers=headers)
                data = r.json().get('data', [])
                if not data: break
                
                for m in data:
                    # REMOVED SCORED CHECK. We trust the scores exist.
                    
                    alliances = m.get('alliances')
                    
                    # Logic Branching
                    r_ids, b_ids = [], []
                    r_score, b_score = 0, 0
                    
                    if isinstance(alliances, list):
                        # List Format (WPI)
                        (r_score, r_ids), (b_score, b_ids) = extract_from_list_format(alliances, debug=(debug_prints < 3))
                    elif isinstance(alliances, dict):
                        # Dict Format (Standard)
                        # ... (Standard extraction logic if needed, but WPI is List)
                        pass

                    # ERROR TRAP: If we still have empty IDs, shout about it (first 3 times only)
                    if (not r_ids or not b_ids) and debug_prints < 3:
                        print(f"\n[DEBUG ALERT] Match {m['id']} skipped. IDs empty.")
                        debug_prints += 1

                    if r_ids and b_ids:
                        match_count += 1
                        for name, s in stats.items():
                            if s['Team_ID'] in r_ids: s['Scores'].append(r_score)
                            if s['Team_ID'] in b_ids: s['Scores'].append(b_score)
                
                sys.stdout.write(f"\r      > Scanned {match_count} matches...")
                sys.stdout.flush()
                page += 1
            except Exception as e: 
                print(f"\n      ⚠️ Error scanning page: {e}")
                break

    # 3. METRICS
    print(f"\n   🔍 CATEGORIZING TEAMS...")
    final_list = []
    
    for name, s in stats.items():
        if len(s['Scores']) > 0:
            s['Avg_Pts'] = round(sum(s['Scores'])/len(s['Scores']), 1)
        
        has_dna = s['Auto'] >= 6.0
        is_high_scorer = s['Avg_Pts'] >= MIN_AVG_POINTS
        played_tough_teams = s['SP'] >= MIN_SP_STRENGTH
        
        status = "Normal"
        tier_score = 0
        
        if has_dna:
            if is_high_scorer and played_tough_teams:
                status = "🏆 TIER 1: CERTIFIED KILLER"
                tier_score = 100
            elif is_high_scorer:
                status = "⚔️ TIER 2: OFFENSIVE THREAT"
                tier_score = 75
            else:
                status = "🧪 TIER 3: UNPROVEN / SPECIALIST"
                tier_score = 50
        elif is_high_scorer:
            status = "🔫 GUNSLINGER (No Auto)"
            tier_score = 40
        elif s['Rank'] <= 10:
             status = "⚠️ FRAUD WATCH"
             tier_score = -20

        sort_val = tier_score + (100 / (s['Rank'] + 1))
        
        final_list.append({
            "Team": name, "Status": status, "Rank": s['Rank'],
            "Auto": s['Auto'], "Avg_Pts": s['Avg_Pts'], "SP": s['SP'],
            "Sort_Val": sort_val
        })

    return pd.DataFrame(final_list)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    sid = get_push_back_id(API_KEY)
    df = scan_my_comp(MY_COMP_SKU, API_KEY, sid)
    
    if df is not None and not df.empty:
        print("\n" + "▓"*80)
        print("🏆 TIER 1: CERTIFIED KILLERS (Auto > 6.0 + Avg Pts > 35)")
        print("▓"*80)
        t1 = df[df['Status'].str.contains("TIER 1")].sort_values(by='Sort_Val', ascending=False)
        if not t1.empty:
            print(t1[['Team', 'Status', 'Rank', 'Auto', 'Avg_Pts', 'SP']].to_string(index=False))
        else: print("No Tier 1 teams found.")

        print("\n" + "="*80)
        print("⚔️ TIER 2: OFFENSIVE THREATS (High Auto + High Scoring)")
        print("="*80)
        t2 = df[df['Status'].str.contains("TIER 2")].sort_values(by='Sort_Val', ascending=False)
        if not t2.empty:
            print(t2[['Team', 'Rank', 'Auto', 'Avg_Pts', 'SP']].to_string(index=False))

        print("\n" + "="*80)
        print("🧪 TIER 3: UNPROVEN / SPECIALISTS (High Auto Only)")
        print("="*80)
        t3 = df[df['Status'].str.contains("TIER 3")].sort_values(by='Sort_Val', ascending=False)
        if not t3.empty:
            print(t3[['Team', 'Rank', 'Auto', 'Avg_Pts', 'SP']].to_string(index=False))
            
        print("\n" + "="*80)
        print("🔫 GUNSLINGERS (High Scoring, No Auto)")
        print("="*80)
        gs = df[df['Status'].str.contains("GUNSLINGER")].sort_values(by='Avg_Pts', ascending=False)
        if not gs.empty:
            print(gs[['Team', 'Rank', 'Auto', 'Avg_Pts']].to_string(index=False))
            
        df.sort_values(by='Sort_Val', ascending=False).to_csv("steintracker_v6_1.csv", index=False)
        print(f"\n✅ Data saved to steintracker_v6_1.csv")