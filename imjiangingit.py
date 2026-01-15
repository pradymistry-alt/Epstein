import requests
import pandas as pd
import numpy as np
import sys
import time

# ==============================================================================
#  IAMJIANGINGIT v3 - ULTIMATE ALLIANCE SELECTION TOOL
#  Combines historical wins, match scoring, consistency, and trends
# ==============================================================================

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"
TARGET_SKU = "RE-V5RC-25-0179"

def get_push_back_id(api_key):
    """Find Season ID for Push Back"""
    print(f"[INFO] Finding Season ID for 'Push Back'...")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    try:
        url = "https://www.robotevents.com/api/v2/seasons?program[]=1"
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        
        for season in r.json()['data']:
            if "Push Back" in season['name']:
                print(f"       ✅ Found: {season['name']} (ID: {season['id']})")
                return season['id']
        
        return r.json()['data'][-1]['id']
    except Exception as e:
        print(f"[ERROR] Could not connect: {e}")
        sys.exit()

def extract_from_list_format(alliance_list):
    """Parse alliance scoring from list format"""
    r_score, r_ids = 0, []
    b_score, b_ids = 0, []
    
    for a in alliance_list:
        color = a.get('color')
        score = a.get('score', 0)
        
        ids = []
        if 'teams' in a:
            for t_item in a['teams']:
                if 'team' in t_item and 'id' in t_item['team']:
                    ids.append(t_item['team']['id'])
                elif 'id' in t_item:
                    ids.append(t_item['id'])
        
        if color == 'red':
            r_score, r_ids = score, ids
        elif color == 'blue':
            b_score, b_ids = score, ids
    
    return (r_score, r_ids), (b_score, b_ids)

def analyze_event(sku, api_key, season_id):
    """Main analysis function combining all metrics"""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    print("\n" + "="*80)
    print("🔍 PHASE 1: EVENT CONNECTION & DATA DOWNLOAD")
    print("="*80)
    
    # Connect to event
    try:
        r = requests.get(f"https://www.robotevents.com/api/v2/events?sku={sku}&include=divisions", headers=headers)
        r.raise_for_status()
        event_data = r.json()['data'][0]
        event_id = event_data['id']
        divisions = event_data.get('divisions', [])
        print(f"✅ Connected: {event_data['name']}")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return None
    
    stats = {}
    
    # Step 1: Rankings
    print(f"\n[1/4] Downloading Rankings...")
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
                    total = t['wins'] + t['losses'] + t['ties']
                    if total == 0: continue
                    
                    stats[name] = {
                        "Team_ID": t_id,
                        "Rank": t['rank'],
                        "Record": f"{t['wins']}-{t['losses']}-{t['ties']}",
                        "Auto": round(t['ap'] / total, 2),
                        "WP": round(t['wp'] / total, 2),
                        "SP": round(t['sp'] / total, 1),
                        "Scores": [],
                        "Past_Wins": 0,
                        "Skills": 0
                    }
                page += 1
            except: break
    
    print(f"   ✅ Loaded {len(stats)} teams")
    
    # Step 2: Skills
    print(f"[2/4] Downloading Skills Scores...")
    page = 1
    while True:
        r = requests.get(f"https://www.robotevents.com/api/v2/events/{event_id}/skills?per_page=100&page={page}", headers=headers)
        data = r.json().get('data', [])
        if not data: break
        for t in data:
            name = t['team']['name']
            if name in stats:
                stats[name]['Skills'] = max(stats[name]['Skills'], t['score'])
        page += 1
    
    # Step 3: Match Scores
    print(f"[3/4] Downloading Match Scores...")
    match_count = 0
    for div in divisions:
        page = 1
        while True:
            m_url = f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/matches?per_page=100&page={page}"
            try:
                r = requests.get(m_url, headers=headers)
                data = r.json().get('data', [])
                if not data: break
                
                for m in data:
                    alliances = m.get('alliances')
                    
                    if isinstance(alliances, list):
                        (r_score, r_ids), (b_score, b_ids) = extract_from_list_format(alliances)
                    elif isinstance(alliances, dict):
                        # Standard dict format
                        r_ids = [t['team']['id'] for t in alliances.get('red', {}).get('teams', [])]
                        b_ids = [t['team']['id'] for t in alliances.get('blue', {}).get('teams', [])]
                        r_score = alliances.get('red', {}).get('score', 0)
                        b_score = alliances.get('blue', {}).get('score', 0)
                    else:
                        continue
                    
                    if r_ids and b_ids:
                        match_count += 1
                        for name, s in stats.items():
                            if s['Team_ID'] in r_ids:
                                s['Scores'].append(r_score)
                            if s['Team_ID'] in b_ids:
                                s['Scores'].append(b_score)
                
                sys.stdout.write(f"\r   Processed {match_count} matches...")
                sys.stdout.flush()
                page += 1
            except: break
    
    print(f"\n   ✅ Analyzed {match_count} matches")
    
    # Step 4: Historical Wins
    print(f"[4/4] Scanning Season History for Past Wins...")
    count = 0
    for name, s in stats.items():
        count += 1
        sys.stdout.write(f"\r   Scanning {count}/{len(stats)}: {name[:30]}...")
        sys.stdout.flush()
        
        try:
            award_url = f"https://www.robotevents.com/api/v2/teams/{s['Team_ID']}/awards?season[]={season_id}"
            ar = requests.get(award_url, headers=headers)
            for a in ar.json().get('data', []):
                title = a['title']
                if "Champion" in title or "Excellence" in title or "Finalist" in title:
                    s['Past_Wins'] += 1
        except: pass
    
    print(f"\n   ✅ Historical data loaded")
    
    # Calculate Advanced Metrics
    print("\n" + "="*80)
    print("🧮 PHASE 2: CALCULATING ADVANCED METRICS")
    print("="*80)
    
    final_list = []
    
    for name, s in stats.items():
        # Basic Metrics
        if len(s['Scores']) > 0:
            s['Avg_Pts'] = round(sum(s['Scores']) / len(s['Scores']), 1)
        else:
            s['Avg_Pts'] = 0
        
        # Consistency (Standard Deviation)
        if len(s['Scores']) > 2:
            s['Std_Dev'] = round(np.std(s['Scores']), 1)
        else:
            s['Std_Dev'] = 0
        
        # Trend Analysis (Early vs Late performance)
        if len(s['Scores']) >= 5:
            split = max(2, len(s['Scores']) // 2)
            early = s['Scores'][:split]
            late = s['Scores'][-split:]
            early_avg = sum(early) / len(early)
            late_avg = sum(late) / len(late)
            trend_delta = round(late_avg - early_avg, 1)
            
            if trend_delta > 5:
                s['Trend'] = "↑"
                s['Trend_Delta'] = trend_delta
            elif trend_delta < -5:
                s['Trend'] = "↓"
                s['Trend_Delta'] = trend_delta
            else:
                s['Trend'] = "→"
                s['Trend_Delta'] = 0
        else:
            s['Trend'] = "→"
            s['Trend_Delta'] = 0
        
        final_list.append({
            "Team": name,
            "Team_ID": s['Team_ID'],
            "Rank": s['Rank'],
            "Record": s['Record'],
            "Auto": s['Auto'],
            "SP": s['SP'],
            "Avg_Pts": s['Avg_Pts'],
            "Std_Dev": s['Std_Dev'],
            "Trend": s['Trend'],
            "Trend_Delta": s['Trend_Delta'],
            "Skills": s['Skills'],
            "Past_Wins": s['Past_Wins']
        })
    
    df = pd.DataFrame(final_list)
    
    # Calculate Dynamic Thresholds (Percentiles)
    p75_pts = df['Avg_Pts'].quantile(0.75)
    p75_auto = df['Auto'].quantile(0.75)
    p50_sp = df['SP'].quantile(0.50)
    
    print(f"   📊 Dynamic Thresholds Calculated:")
    print(f"      75th %ile Avg Points: {p75_pts:.1f}")
    print(f"      75th %ile Auto: {p75_auto:.1f}")
    print(f"      Median SP: {p50_sp:.1f}")
    
    # Categorization
    print("\n" + "="*80)
    print("🏷️  PHASE 3: TEAM CATEGORIZATION")
    print("="*80)
    
    categories = []
    tier_scores = []
    
    for idx, row in df.iterrows():
        has_strong_auto = row['Auto'] >= p75_auto
        is_high_scorer = row['Avg_Pts'] >= p75_pts
        is_consistent = row['Std_Dev'] < 12
        is_improving = row['Trend'] == "↑"
        played_tough = row['SP'] >= p50_sp
        
        # Category Logic
        if row['Rank'] <= 5 and row['Past_Wins'] >= 1 and is_high_scorer:
            category = "🏆 ELITE"
            tier = 100
        
        elif row['Rank'] >= 10 and (row['Past_Wins'] > 0 or (is_improving and is_consistent)):
            category = "🚀 SLEEPER"
            tier = 90
        
        elif row['Rank'] <= 8 and row['Past_Wins'] == 0 and row['SP'] < p50_sp:
            category = "⚠️ FRAUD WATCH"
            tier = 20
        
        elif 11 <= row['Rank'] <= 20 and is_consistent and is_improving:
            category = "🎯 DARK HORSE"
            tier = 85
        
        elif is_high_scorer and not has_strong_auto:
            category = "🔫 GUNSLINGER"
            tier = 60
        
        elif has_strong_auto and not is_high_scorer:
            category = "🧪 SPECIALIST"
            tier = 55
        
        elif is_improving and row['Trend_Delta'] >= 8:
            category = "⚡ PEAKING"
            tier = 75
        
        else:
            category = "📊 SOLID"
            tier = 50
        
        # Composite Score for sorting
        composite = tier + (100 / (row['Rank'] + 1)) + (row['Past_Wins'] * 10)
        
        categories.append(category)
        tier_scores.append(round(composite, 2))
    
    df['Category'] = categories
    df['Tier_Score'] = tier_scores
    
    return df

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("\n" + "▓"*80)
    print("   🤖 IAMJIANGINGIT v3 - ULTIMATE ALLIANCE SELECTION")
    print("▓"*80)
    
    season_id = get_push_back_id(API_KEY)
    df = analyze_event(TARGET_SKU, API_KEY, season_id)
    
    if df is not None and not df.empty:
        # Save full data
        df.sort_values(by='Tier_Score', ascending=False).to_csv("iamjiangingit_v3_full.csv", index=False)
        
        print("\n" + "▓"*80)
        print("🏆 ELITE TIER (Top 5 Rank + Past Wins + High Scoring)")
        print("▓"*80)
        elite = df[df['Category'] == "🏆 ELITE"].sort_values(by='Tier_Score', ascending=False)
        if not elite.empty:
            print(elite[['Team', 'Rank', 'Auto', 'Avg_Pts', 'Past_Wins', 'Skills']].to_string(index=False))
        else:
            print("No Elite teams found.")
        
        print("\n" + "="*80)
        print("🚀 SLEEPERS (Rank 10+ but Has Wins OR Improving Trend)")
        print("="*80)
        sleepers = df[df['Category'] == "🚀 SLEEPER"].sort_values(by='Tier_Score', ascending=False)
        if not sleepers.empty:
            print(sleepers[['Team', 'Rank', 'Avg_Pts', 'Trend', 'Past_Wins', 'Std_Dev']].to_string(index=False))
        else:
            print("No sleepers detected.")
        
        print("\n" + "="*80)
        print("⚠️ FRAUD WATCH (Top 8 Rank but NO Wins + Low Schedule Strength)")
        print("="*80)
        frauds = df[df['Category'] == "⚠️ FRAUD WATCH"].sort_values(by='Rank')
        if not frauds.empty:
            print(frauds[['Team', 'Rank', 'Record', 'SP', 'Past_Wins']].to_string(index=False))
        else:
            print("✅ Top 8 are all legit!")
        
        print("\n" + "="*80)
        print("🎯 DARK HORSES (Mid-Rank + Consistent + Improving)")
        print("="*80)
        dark = df[df['Category'] == "🎯 DARK HORSE"].sort_values(by='Tier_Score', ascending=False)
        if not dark.empty:
            print(dark[['Team', 'Rank', 'Avg_Pts', 'Trend', 'Std_Dev']].to_string(index=False))
        else:
            print("No dark horses found.")
        
        print("\n" + "="*80)
        print("⚡ PEAKING TEAMS (Strong Upward Trend)")
        print("="*80)
        peaking = df[df['Category'] == "⚡ PEAKING"].sort_values(by='Trend_Delta', ascending=False)
        if not peaking.empty:
            print(peaking[['Team', '
            Rank', 'Trend_Delta', 'Avg_Pts']].to_string(index=False))
        else:
            print("No peaking teams.")
        
        print("\n" + "="*80)
        print("🔫 GUNSLINGERS (High Scoring but Weak Auto)")
        print("="*80)
        guns = df[df['Category'] == "🔫 GUNSLINGER"].sort_values(by='Avg_Pts', ascending=False)
        if not guns.empty:
            print(guns[['Team', 'Rank', 'Auto', 'Avg_Pts']].to_string(index=False))
        
        print("\n" + "="*80)
        print("📊 TOP 15 OVERALL (By Composite Score)")
        print("="*80)
        top15 = df.sort_values(by='Tier_Score', ascending=False).head(15)
        print(top15[['Team', 'Category', 'Rank', 'Avg_Pts', 'Past_Wins', 'Tier_Score']].to_string(index=False))
        
        print("\n" + "="*80)
        print(f"✅ Full dataset saved to: iamjiangingit_v3_full.csv")
        print(f"   Total teams analyzed: {len(df)}")
        print("="*80)