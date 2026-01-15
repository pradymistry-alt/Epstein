import requests
import pandas as pd
import numpy as np
import sys
import joblib
import os

# ==============================================================================
#  IAMJIANGINGIT v4 - FINAL EDITION
#  Most accurate ML predictions + Personalized for YOUR team
# ==============================================================================

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"

# ==============================================================================
# PERSONALIZATION SETTINGS
# ==============================================================================
MY_TEAM = "8568A"  # Set to your team number (or "" to disable personalization)
TARGET_SKU = "RE-V5RC-25-9994"  # Your event

# Feature importance weights (adjust based on your priorities)
FEATURE_WEIGHTS = {
    "Auto": 1.5,      # Programming is 50% more important
    "Avg_Pts": 0.7,   # Driver skills less important
    # Other features keep default weight of 1.0
}

def get_push_back_id(api_key):
    """Find Season ID for Push Back"""
    print(f"[INFO] Finding Season ID...")
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

def calculate_synergy(my_stats, partner_stats):
    """
    Calculate how well a partner complements YOUR team
    Returns synergy score (higher = better match)
    """
    synergy_score = 0
    
    # 1. AUTO SYNERGY (Critical for you!)
    if my_stats['Auto'] >= 6 and partner_stats['Auto'] >= 6:
        synergy_score += 30  # Double auto = amazing
    elif partner_stats['Auto'] >= 6:
        synergy_score += 20  # Partner has strong auto
    elif partner_stats['Auto'] < 4 and my_stats['Auto'] < 4:
        synergy_score -= 15  # Both weak = bad
    
    # 2. SCORING SYNERGY
    combined_scoring = my_stats['Avg_Pts'] + partner_stats['Avg_Pts']
    if combined_scoring >= 80:
        synergy_score += 25
    elif combined_scoring >= 65:
        synergy_score += 15
    elif combined_scoring < 50:
        synergy_score -= 10
    
    # 3. CONSISTENCY (Want reliable partner)
    if partner_stats['Std_Dev'] < 10:
        synergy_score += 15
    elif partner_stats['Std_Dev'] > 20:
        synergy_score -= 10
    
    # 4. COMPLEMENTARY STRENGTHS
    if my_stats['Avg_Pts'] < 35 and partner_stats['Avg_Pts'] >= 40:
        synergy_score += 10
    if my_stats['Auto'] < 5 and partner_stats['Auto'] >= 7:
        synergy_score += 15
    
    # 5. AVOID DOUBLE WEAKNESS
    if my_stats['Auto'] < 4 and partner_stats['Auto'] < 4:
        synergy_score -= 20
    
    return synergy_score

def analyze_event_ml(sku, api_key, season_id, model_data, my_team=None):
    """Main analysis function with ML predictions"""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    print("\n" + "="*80)
    print("🔍 PHASE 1: EVENT DATA COLLECTION")
    if my_team:
        print(f"   Personalized for: {my_team}")
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
        return None, None
    
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
    print(f"[4/4] Scanning Season History...")
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
    
    # Calculate metrics
    print("\n" + "="*80)
    print("🧮 PHASE 2: CALCULATING METRICS & ML PREDICTIONS")
    print("="*80)
    
    final_list = []
    my_team_stats = None
    
    for name, s in stats.items():
        # Basic metrics
        if len(s['Scores']) > 0:
            avg_pts = round(sum(s['Scores']) / len(s['Scores']), 1)
            std_dev = round(np.std(s['Scores']), 1) if len(s['Scores']) > 2 else 0
        else:
            avg_pts = 0
            std_dev = 0
        
        # Trend
        if len(s['Scores']) >= 5:
            split = max(2, len(s['Scores']) // 2)
            early = s['Scores'][:split]
            late = s['Scores'][-split:]
            trend_delta = round((sum(late)/len(late)) - (sum(early)/len(early)), 1)
            trend = "↑" if trend_delta > 5 else "↓" if trend_delta < -5 else "→"
        else:
            trend_delta = 0
            trend = "→"
        
        # QUALITY SCORE: Weights SP heavily to value wins against strong teams
        # Formula: (Avg_Pts * 0.6) + (SP * 0.3) + (Win% * 10)
        win_pct = s['WP']
        quality_score = round((avg_pts * 0.6) + (s['SP'] * 0.3) + (win_pct * 10), 1)
        
        team_data = {
            "Team": name,
            "Team_ID": s['Team_ID'],
            "Rank": s['Rank'],
            "Record": s['Record'],
            "Auto": s['Auto'],
            "SP": s['SP'],
            "Avg_Pts": avg_pts,
            "Quality_Score": quality_score,
            "Std_Dev": std_dev,
            "Trend": trend,
            "Trend_Delta": trend_delta,
            "Skills": s['Skills'],
            "Past_Wins": s['Past_Wins']
        }
        
        # Save YOUR team's stats if personalization enabled
        if my_team and name == my_team:
            my_team_stats = team_data.copy()
            print(f"\n📍 FOUND YOUR TEAM: {my_team}")
            print(f"   Rank: {s['Rank']} | Auto: {s['Auto']} | Avg Pts: {avg_pts}")
        
        final_list.append(team_data)
    
    df = pd.DataFrame(final_list)
    
    # ML PREDICTIONS with optional weighting
    print("\n🤖 Running ML Predictions...")
    model = model_data['model']
    feature_cols = model_data['feature_cols']
    
    # Prepare features
    X = df[feature_cols].fillna(0).copy()
    
    # Apply custom weights if provided
    if FEATURE_WEIGHTS:
        print("   🎯 Applying custom feature weights (Auto prioritized)...")
        for col, weight in FEATURE_WEIGHTS.items():
            if col in X.columns:
                X[col] = X[col] * weight
    
    # Get predictions
    df['ML_Win_Prob'] = model.predict_proba(X)[:, 1]
    df['ML_Prediction'] = model.predict(X)
    
    # ML Categories
    df['ML_Tier'] = df['ML_Win_Prob'].apply(
        lambda x: "🎯 ML TOP PICK" if x >= 0.70 else
                  "✅ ML STRONG" if x >= 0.50 else
                  "⚠️ ML RISKY" if x >= 0.30 else
                  "❌ ML AVOID"
    )
    
    print(f"   ✅ ML predictions complete")
    print(f"   📊 {len(df[df['ML_Win_Prob'] >= 0.70])} teams rated as TOP PICKS (70%+ win prob)")
    
    # Calculate dynamic thresholds for traditional categories
    p75_pts = df['Avg_Pts'].quantile(0.75)
    p75_auto = df['Auto'].quantile(0.75)
    p50_sp = df['SP'].quantile(0.50)
    
    # Traditional categorization
    traditional_cats = []
    tier_scores = []
    
    for idx, row in df.iterrows():
        has_strong_auto = row['Auto'] >= p75_auto
        is_high_scorer = row['Avg_Pts'] >= p75_pts
        is_consistent = row['Std_Dev'] < 12
        is_improving = row['Trend'] == "↑"
        
        if row['Rank'] <= 5 and row['Past_Wins'] >= 1 and is_high_scorer:
            cat = "🏆 ELITE"
            tier = 100
        elif row['Rank'] >= 10 and (row['Past_Wins'] > 0 or (is_improving and is_consistent)):
            cat = "🚀 SLEEPER"
            tier = 90
        elif row['Rank'] <= 8 and row['Past_Wins'] == 0 and row['SP'] < p50_sp:
            cat = "⚠️ FRAUD"
            tier = 20
        elif 11 <= row['Rank'] <= 20 and is_consistent and is_improving:
            cat = "🎯 DARK HORSE"
            tier = 85
        elif is_improving and row['Trend_Delta'] >= 8:
            cat = "⚡ PEAKING"
            tier = 75
        elif is_high_scorer and not has_strong_auto:
            cat = "🔫 GUNSLINGER"
            tier = 60
        else:
            cat = "📊 SOLID"
            tier = 50
        
        traditional_cats.append(cat)
        
        # Composite score
        composite = (row['ML_Win_Prob'] * 100) + (100 / (row['Rank'] + 1)) + (row['Past_Wins'] * 10)
        tier_scores.append(round(composite, 2))
    
    df['Traditional_Cat'] = traditional_cats
    df['Composite_Score'] = tier_scores
    
    # CALCULATE SYNERGY if personalization enabled
    if my_team and my_team_stats:
        print("\n🤝 Calculating partner synergy scores...")
        synergy_scores = []
        for idx, row in df.iterrows():
            if row['Team'] == my_team:
                synergy_scores.append(0)
            else:
                synergy = calculate_synergy(my_team_stats, row)
                synergy_scores.append(synergy)
        
        df['Synergy_Score'] = synergy_scores
        df['Partner_Score'] = (
            df['ML_Win_Prob'] * 100 +
            df['Synergy_Score'] +
            (100 / (df['Rank'] + 1))
        )
    else:
        df['Synergy_Score'] = 0
        df['Partner_Score'] = df['Composite_Score']
    
    return df, my_team_stats

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("\n" + "▓"*80)
    if MY_TEAM:
        print(f"   🤖 IAMJIANGINGIT v4 - PERSONALIZED FOR {MY_TEAM}")
    else:
        print("   🤖 IAMJIANGINGIT v4 - ML EDITION")
    print("   Most Accurate ML + Alliance Selection")
    print("▓"*80)
    
    # Load ML model
    if not os.path.exists('alliance_predictor.pkl'):
        print("\n❌ ERROR: alliance_predictor.pkl not found!")
        print("   You need to run train_model.py first.")
        sys.exit()
    
    print("\n📂 Loading trained ML model...")
    model_data = joblib.load('alliance_predictor.pkl')
    print("   ✅ Model loaded successfully")
    
    # Get season and analyze
    season_id = get_push_back_id(API_KEY)
    df, my_stats = analyze_event_ml(TARGET_SKU, API_KEY, season_id, model_data, MY_TEAM if MY_TEAM else None)
    
    if df is not None and not df.empty:
        # Save full data
        df.sort_values(by='Partner_Score', ascending=False).to_csv("v4_final_report.csv", index=False)
        
        # PERSONALIZED REPORT (if enabled)
        if MY_TEAM and my_stats:
            my_rank = my_stats['Rank']
            
            # REALISTIC PARTNERS: Only teams YOU can pick (ranked below you)
            print("\n" + "▓"*80)
            print(f"🎯 BEST PICKS FOR {MY_TEAM} (Rank {my_rank})")
            print(f"   Teams YOU can select (ranked below you)")
            print("▓"*80)
            
            # Only show teams ranked below you
            pickable_teams = df[
                (df['Team'] != MY_TEAM) & 
                (df['Rank'] > my_rank)
            ].sort_values(by='Partner_Score', ascending=False).head(15)
            
            if not pickable_teams.empty:
                print(pickable_teams[['Team', 'Rank', 'Auto', 'Quality_Score', 'Avg_Pts', 'SP', 'ML_Win_Prob', 'Synergy_Score', 'Traditional_Cat']].to_string(index=False))
            else:
                print(f"   ⚠️ No teams ranked below you (you're ranked {my_rank})")
                print("   You'll likely be picked by a higher-ranked team.")
            
            # Show breakdown by category for teams you can pick
            if not pickable_teams.empty:
                print("\n" + "="*80)
                print("📊 YOUR PICKABLE TEAMS BY CATEGORY:")
                print("="*80)
                
                sleepers = pickable_teams[pickable_teams['Traditional_Cat'] == '🚀 SLEEPER']
                dark_horses = pickable_teams[pickable_teams['Traditional_Cat'] == '🎯 DARK HORSE']
                specialists = pickable_teams[pickable_teams['Traditional_Cat'] == '🧪 SPECIALIST']
                
                if not sleepers.empty:
                    print(f"   🚀 SLEEPERS: {len(sleepers)} teams (best value picks!)")
                    print(f"      Top pick: {sleepers.iloc[0]['Team']} (Rank {sleepers.iloc[0]['Rank']}, ML: {sleepers.iloc[0]['ML_Win_Prob']:.0%})")
                
                if not dark_horses.empty:
                    print(f"   🎯 DARK HORSES: {len(dark_horses)} teams (improving, consistent)")
                    print(f"      Top pick: {dark_horses.iloc[0]['Team']} (Rank {dark_horses.iloc[0]['Rank']}, Trend: {dark_horses.iloc[0]['Trend']})")
                
                if not specialists.empty:
                    print(f"   🧪 AUTO SPECIALISTS: {len(specialists)} teams (strong programming)")
                    print(f"      Top pick: {specialists.iloc[0]['Team']} (Auto: {specialists.iloc[0]['Auto']})")
                
                # Best synergy pick
                best_synergy = pickable_teams.iloc[0]
                print(f"\n   ⭐ RECOMMENDED PICK: {best_synergy['Team']}")
                print(f"      Rank {best_synergy['Rank']} | ML: {best_synergy['ML_Win_Prob']:.0%} | Synergy: +{best_synergy['Synergy_Score']:.0f}")
        
        # STANDARD REPORTS
        print("\n" + "▓"*80)
        print("🎯 ML TOP PICKS (70%+ Win Probability)")
        print("▓"*80)
        top_picks = df[df['ML_Win_Prob'] >= 0.70].sort_values(by='ML_Win_Prob', ascending=False)
        if not top_picks.empty:
            print(top_picks[['Team', 'Rank', 'ML_Win_Prob', 'Auto', 'Avg_Pts', 'Past_Wins']].to_string(index=False))
        else:
            print("No teams with 70%+ probability. Check next tier.")
        
        print("\n" + "="*80)
        print("✅ ML STRONG PICKS (50-70%)")
        print("="*80)
        strong = df[(df['ML_Win_Prob'] >= 0.50) & (df['ML_Win_Prob'] < 0.70)].sort_values(by='ML_Win_Prob', ascending=False)
        if not strong.empty:
            print(strong[['Team', 'Rank', 'ML_Win_Prob', 'Traditional_Cat', 'Auto']].to_string(index=False))
        
        print("\n" + "="*80)
        print("🚨 HIDDEN GEMS (High ML + Low Rank)")
        print("="*80)
        hidden_gems = df[(df['ML_Win_Prob'] >= 0.60) & (df['Rank'] >= 12)].sort_values(by='ML_Win_Prob', ascending=False)
        if not hidden_gems.empty:
            print(hidden_gems[['Team', 'Rank', 'ML_Win_Prob', 'Auto', 'Trend']].to_string(index=False))
        
        print("\n" + "="*80)
        print("⚠️ FRAUD WATCH (Low ML + High Rank)")
        print("   *High risk of first-round exit*")
        print("="*80)
        potential_frauds = df[(df['ML_Win_Prob'] < 0.40) & (df['Rank'] <= 8)].sort_values(by='Rank')
        if not potential_frauds.empty:
            print(potential_frauds[['Team', 'Rank', 'ML_Win_Prob', 'SP', 'Past_Wins']].to_string(index=False))
        else:
            print("✅ Top 8 all look solid!")
        
        print("\n" + "="*80)
        print("🏆 TOP 15 OVERALL")
        print("="*80)
        top15 = df.sort_values(by='Composite_Score', ascending=False).head(15)
        print(top15[['Team', 'Rank', 'ML_Win_Prob', 'Traditional_Cat', 'Auto']].to_string(index=False))
        
        print("\n" + "="*80)
        print("📊 STATISTICS")
        print("="*80)
        print(f"   Total Teams: {len(df)}")
        print(f"   ML Top Picks (70%+): {len(df[df['ML_Win_Prob'] >= 0.70])}")
        print(f"   ML Strong (50-70%): {len(df[(df['ML_Win_Prob'] >= 0.50) & (df['ML_Win_Prob'] < 0.70)])}")
        print(f"   Fraud Watch: {len(df[(df['ML_Win_Prob'] < 0.40) & (df['Rank'] <= 8)])}")
        print(f"   Average ML Win Prob: {df['ML_Win_Prob'].mean():.1%}")
        print(f"   Teams with Past Wins: {len(df[df['Past_Wins'] > 0])}")
        
        if my_stats:
            my_ml = df[df['Team']==MY_TEAM]['ML_Win_Prob'].values[0]
            my_cat = df[df['Team']==MY_TEAM]['Traditional_Cat'].values[0]
            print(f"\n   YOUR TEAM ({MY_TEAM}):")
            print(f"   Rank: {my_stats['Rank']} | Category: {my_cat}")
            print(f"   ML Win Prob: {my_ml:.1%} | Auto: {my_stats['Auto']}")
        
        print("\n" + "="*80)
        print(f"✅ Full report saved to: v4_final_report.csv")
        print("="*80)