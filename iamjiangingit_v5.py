import requests
import pandas as pd
import numpy as np
import sys
import joblib
import os
import time

# ==============================================================================
#  IAMJIANGINGIT v5 - ULTIMATE EDITION
#  Enhanced ML + Push Back Synergy + Availability Prediction + Real-Time Tracking
# ==============================================================================

API_KEY = "YOUR_API_KEY_HERE"  # Replace with your API key

# ==============================================================================
# PERSONALIZATION SETTINGS
# ==============================================================================
MY_TEAM = "8568A"  # Set to your team number
TARGET_SKU = "RE-V5RC-25-9994"  # Your event

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def safe_request(url, headers, delay=0.3, retries=3):
    """Make API request with rate limit protection"""
    time.sleep(delay)
    
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            
            if r.status_code == 429:
                wait = (attempt + 1) * 5
                print(f"   ⏳ Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            
            if r.status_code >= 500:
                return None
                
            return r.json()
            
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(2)
    
    return None

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

# ==============================================================================
# FEATURE 1: CEILING/FLOOR ANALYSIS
# ==============================================================================

def calculate_ceiling_floor(scores):
    """
    Calculate a team's ceiling (best performances) and floor (worst performances)
    This helps identify high-upside vs safe picks
    """
    if len(scores) < 3:
        return {
            'ceiling': max(scores) if scores else 0,
            'floor': min(scores) if scores else 0,
            'upside': 0,
            'downside': 0,
            'volatility_type': 'UNKNOWN'
        }
    
    ceiling = np.percentile(scores, 90)  # Top 10% performances
    floor = np.percentile(scores, 10)    # Bottom 10% performances
    avg = np.mean(scores)
    
    upside = ceiling - avg    # How much BETTER can they be?
    downside = avg - floor    # How much WORSE can they be?
    
    # Categorize volatility type
    if upside > 15 and downside < 10:
        volatility_type = "HIGH_UPSIDE"  # Can pop off, rarely bad
    elif upside < 10 and downside > 15:
        volatility_type = "RISKY"        # Rarely great, can be terrible
    elif upside > 15 and downside > 15:
        volatility_type = "VOLATILE"     # Unpredictable - boom or bust
    else:
        volatility_type = "CONSISTENT"   # What you see is what you get
    
    return {
        'ceiling': round(ceiling, 1),
        'floor': round(floor, 1),
        'upside': round(upside, 1),
        'downside': round(downside, 1),
        'volatility_type': volatility_type
    }

# ==============================================================================
# FEATURE 2: CLUTCH PERFORMANCE ANALYSIS
# ==============================================================================

def calculate_clutch_factor(match_data, team_id):
    """
    Analyze how a team performs in close matches
    Clutch teams win tight games; chokers lose them
    """
    close_wins = 0
    close_losses = 0
    blowout_wins = 0
    blowout_losses = 0
    
    for match in match_data:
        if team_id not in match['team_ids']:
            continue
        
        team_score = match['team_score']
        opp_score = match['opp_score']
        margin = team_score - opp_score
        
        is_close = abs(margin) <= 10  # Within 10 points = close match
        won = margin > 0
        
        if is_close:
            if won:
                close_wins += 1
            else:
                close_losses += 1
        else:
            if won:
                blowout_wins += 1
            else:
                blowout_losses += 1
    
    total_close = close_wins + close_losses
    clutch_rate = close_wins / total_close if total_close > 0 else 0.5
    
    # Clutch rating: >0.6 = clutch, <0.4 = choker
    if clutch_rate >= 0.65 and total_close >= 3:
        clutch_label = "🧊 CLUTCH"
    elif clutch_rate <= 0.35 and total_close >= 3:
        clutch_label = "😰 CHOKER"
    else:
        clutch_label = "➖ NEUTRAL"
    
    return {
        'close_wins': close_wins,
        'close_losses': close_losses,
        'clutch_rate': round(clutch_rate, 2),
        'clutch_label': clutch_label,
        'total_close_matches': total_close
    }

# ==============================================================================
# FEATURE 3: PUSH BACK SPECIFIC SYNERGY
# ==============================================================================

def calculate_push_back_synergy(my_stats, partner_stats):
    """
    Calculate synergy specifically for Push Back game mechanics
    This is customized for the 2024-25 VEX game
    """
    synergy = 0
    reasons = []
    
    # ==========================================================================
    # AUTO SYNERGY (CRITICAL IN PUSH BACK)
    # ==========================================================================
    my_auto = my_stats.get('Auto', 0)
    partner_auto = partner_stats.get('Auto', 0)
    combined_auto = my_auto + partner_auto
    
    if combined_auto >= 14:
        synergy += 40
        reasons.append("🔥 ELITE combined auto")
    elif combined_auto >= 12:
        synergy += 30
        reasons.append("✅ Strong combined auto")
    elif combined_auto >= 10:
        synergy += 15
        reasons.append("👍 Decent combined auto")
    elif combined_auto < 8:
        synergy -= 30
        reasons.append("⚠️ WEAK auto - will lose AWP")
    
    # Bonus if partner covers your auto weakness
    if my_auto < 5 and partner_auto >= 7:
        synergy += 20
        reasons.append("🎯 Partner covers your auto weakness")
    
    # ==========================================================================
    # SCORING SYNERGY
    # ==========================================================================
    my_avg = my_stats.get('Avg_Pts', 0)
    partner_avg = partner_stats.get('Avg_Pts', 0)
    combined_scoring = my_avg + partner_avg
    
    if combined_scoring >= 90:
        synergy += 35
        reasons.append("💪 Elite combined scoring")
    elif combined_scoring >= 75:
        synergy += 25
        reasons.append("✅ Strong combined scoring")
    elif combined_scoring >= 60:
        synergy += 10
    elif combined_scoring < 50:
        synergy -= 20
        reasons.append("⚠️ Low combined scoring potential")
    
    # ==========================================================================
    # CONSISTENCY SYNERGY
    # ==========================================================================
    my_std = my_stats.get('Std_Dev', 0)
    partner_std = partner_stats.get('Std_Dev', 0)
    
    # You want at least ONE consistent team
    if partner_std < 8:
        synergy += 20
        reasons.append("🎯 Partner is very consistent")
    elif partner_std < 12:
        synergy += 10
    elif partner_std > 20:
        synergy -= 15
        reasons.append("⚠️ Partner is unpredictable")
    
    # If YOU'RE inconsistent, you NEED a consistent partner
    if my_std > 15 and partner_std > 15:
        synergy -= 25
        reasons.append("❌ Both teams inconsistent - dangerous")
    
    # ==========================================================================
    # COMPLEMENTARY STRENGTHS
    # ==========================================================================
    # If you're a scorer, find someone consistent
    if my_avg >= 40 and partner_std < 10:
        synergy += 15
        reasons.append("👍 Consistent partner for your scoring")
    
    # If you're weaker, find a carry
    if my_avg < 30 and partner_avg >= 45:
        synergy += 20
        reasons.append("💪 Partner can carry scoring load")
    
    # ==========================================================================
    # MOMENTUM/TREND SYNERGY
    # ==========================================================================
    partner_trend = partner_stats.get('Trend_Delta', 0)
    
    if partner_trend >= 8:
        synergy += 15
        reasons.append("📈 Partner is improving/peaking")
    elif partner_trend <= -8:
        synergy -= 15
        reasons.append("📉 Partner is declining")
    
    # ==========================================================================
    # CEILING POTENTIAL (for elims)
    # ==========================================================================
    partner_ceiling = partner_stats.get('ceiling', partner_avg)
    partner_upside = partner_stats.get('upside', 0)
    
    if partner_upside >= 15:
        synergy += 10
        reasons.append("🚀 Partner has high ceiling")
    
    # Combined ceiling check
    my_ceiling = my_stats.get('ceiling', my_avg)
    if my_ceiling + partner_ceiling >= 100:
        synergy += 15
        reasons.append("💥 Elite combined ceiling for elims")
    
    return {
        'synergy_score': synergy,
        'reasons': reasons,
        'combined_auto': combined_auto,
        'combined_scoring': combined_scoring
    }

# ==============================================================================
# FEATURE 4: AVAILABILITY PREDICTION
# ==============================================================================

def predict_availability(team_data, my_pick_position, all_teams_df):
    """
    Predict if a team will still be available when you pick
    
    Logic:
    - Teams ranked above you pick before you
    - They'll likely pick high-value teams
    - Hidden gems (low rank + high ML) are more likely available
    """
    team_rank = team_data['Rank']
    team_ml = team_data['ML_Win_Prob']
    team_quality = team_data.get('Quality_Score', 0)
    
    # Count how many teams pick before you
    teams_picking_before = my_pick_position - 1
    
    # Estimate "desirability" - how likely other captains will want this team
    desirability = (team_ml * 50) + (team_quality * 0.5) + (50 / (team_rank + 1))
    
    # High rank + high ML = obvious pick = likely taken
    if team_rank <= 12 and team_ml >= 0.6:
        availability = "🔴 LIKELY TAKEN"
        avail_score = 0.2
    # Low rank + high ML = hidden gem = likely available
    elif team_rank >= 16 and team_ml >= 0.5:
        availability = "🟢 LIKELY AVAILABLE"
        avail_score = 0.85
    # Mid rank, decent stats = toss-up
    elif team_rank >= 12 and team_rank <= 20:
        if team_ml >= 0.55:
            availability = "🟡 MAYBE AVAILABLE"
            avail_score = 0.5
        else:
            availability = "🟢 LIKELY AVAILABLE"
            avail_score = 0.75
    # Low rank, low ML = definitely available but not great
    elif team_rank >= 20 and team_ml < 0.4:
        availability = "🟢 AVAILABLE (but weak)"
        avail_score = 0.95
    else:
        availability = "🟡 UNCERTAIN"
        avail_score = 0.5
    
    return {
        'availability': availability,
        'availability_score': avail_score,
        'desirability': round(desirability, 1)
    }

# ==============================================================================
# FEATURE 5: UPSET POTENTIAL
# ==============================================================================

def calculate_upset_potential(wins_vs_higher, losses_vs_higher, wins_vs_lower, losses_vs_lower):
    """
    Calculate how often a team beats higher-ranked opponents
    High upset potential = dangerous in elims
    """
    total_vs_higher = wins_vs_higher + losses_vs_higher
    total_vs_lower = wins_vs_lower + losses_vs_lower
    
    upset_rate = wins_vs_higher / total_vs_higher if total_vs_higher > 0 else 0
    expected_win_rate = wins_vs_lower / total_vs_lower if total_vs_lower > 0 else 0
    
    if upset_rate >= 0.5 and total_vs_higher >= 3:
        upset_label = "🔥 GIANT KILLER"
    elif upset_rate >= 0.35 and total_vs_higher >= 2:
        upset_label = "⚡ UPSET THREAT"
    elif upset_rate <= 0.2 and total_vs_higher >= 3:
        upset_label = "📉 UNDERPERFORMS"
    else:
        upset_label = "➖ NORMAL"
    
    return {
        'upset_rate': round(upset_rate, 2),
        'upset_label': upset_label,
        'wins_vs_higher': wins_vs_higher,
        'total_vs_higher': total_vs_higher
    }

# ==============================================================================
# FEATURE 6: TIERED RECOMMENDATIONS
# ==============================================================================

def generate_tiered_recommendations(df, my_rank, my_stats):
    """
    Generate three tiers of recommendations based on realistic scenarios
    """
    # Only teams you can pick (ranked below you)
    pickable = df[df['Rank'] > my_rank].copy()
    
    if pickable.empty:
        return None
    
    # Sort by Partner_Score
    pickable = pickable.sort_values('Partner_Score', ascending=False)
    
    # TIER A: Best case - you pick early, get your top choice
    tier_a = pickable.head(3).copy()
    tier_a['Scenario'] = 'A - BEST CASE'
    
    # TIER B: Realistic - your top picks are gone
    tier_b = pickable.iloc[3:8].copy() if len(pickable) > 3 else pd.DataFrame()
    if not tier_b.empty:
        tier_b['Scenario'] = 'B - REALISTIC'
    
    # TIER C: Emergency - find sleepers/dark horses
    tier_c = pickable[
        (pickable['Traditional_Cat'].str.contains('SLEEPER|DARK HORSE', na=False)) |
        (pickable['Upside'] >= 12) |
        ((pickable['ML_Win_Prob'] >= 0.45) & (pickable['Rank'] >= 20))
    ].head(5).copy()
    if not tier_c.empty:
        tier_c['Scenario'] = 'C - EMERGENCY/SLEEPER'
    
    # TIER SAFE: Consistent, reliable teams (low std dev)
    tier_safe = pickable[
        (pickable['Std_Dev'] < 10) & 
        (pickable['ML_Win_Prob'] >= 0.35)
    ].head(5).copy()
    if not tier_safe.empty:
        tier_safe['Scenario'] = 'SAFE - CONSISTENT'
    
    # TIER BOOM: High ceiling teams (for aggressive play)
    tier_boom = pickable[
        (pickable['Upside'] >= 15) |
        (pickable['Volatility_Type'] == 'HIGH_UPSIDE')
    ].head(5).copy()
    if not tier_boom.empty:
        tier_boom['Scenario'] = 'BOOM - HIGH CEILING'
    
    return {
        'tier_a': tier_a,
        'tier_b': tier_b,
        'tier_c': tier_c,
        'tier_safe': tier_safe,
        'tier_boom': tier_boom,
        'all_pickable': pickable
    }

# ==============================================================================
# MAIN ANALYSIS FUNCTION
# ==============================================================================

def analyze_event_v5(sku, api_key, season_id, model_data, my_team=None):
    """Enhanced analysis with all new features"""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    print("\n" + "="*80)
    print("🔍 PHASE 1: EVENT DATA COLLECTION")
    if my_team:
        print(f"   📍 Personalized for: {my_team}")
    print("="*80)
    
    # Connect to event
    try:
        r = requests.get(f"https://www.robotevents.com/api/v2/events?sku={sku}&include=divisions", headers=headers)
        r.raise_for_status()
        event_data = r.json()['data'][0]
        event_id = event_data['id']
        event_name = event_data['name']
        divisions = event_data.get('divisions', [])
        print(f"✅ Connected: {event_name}")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return None, None, None
    
    stats = {}
    match_details = []  # Store detailed match info for clutch analysis
    
    # Step 1: Rankings
    print(f"\n[1/5] Downloading Rankings...")
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
                        "Wins": t['wins'],
                        "Losses": t['losses'],
                        "Auto": round(t['ap'] / total, 2),
                        "WP": round(t['wp'] / total, 2),
                        "SP": round(t['sp'] / total, 1),
                        "Scores": [],
                        "Opponents_Scores": [],
                        "Past_Wins": 0,
                        "Skills": 0,
                        "Wins_vs_Higher": 0,
                        "Losses_vs_Higher": 0,
                        "Wins_vs_Lower": 0,
                        "Losses_vs_Lower": 0
                    }
                page += 1
            except: break
    
    print(f"   ✅ Loaded {len(stats)} teams")
    
    # Create rank lookup for upset tracking
    team_ranks = {s['Team_ID']: s['Rank'] for s in stats.values()}
    
    # Step 2: Skills
    print(f"[2/5] Downloading Skills Scores...")
    page = 1
    while True:
        skills_data = safe_request(f"https://www.robotevents.com/api/v2/events/{event_id}/skills?per_page=100&page={page}", headers)
        if not skills_data or not skills_data.get('data'):
            break
        for t in skills_data['data']:
            name = t['team']['name']
            if name in stats:
                stats[name]['Skills'] = max(stats[name]['Skills'], t['score'])
        page += 1
    
    # Step 3: Match Scores (Enhanced with opponent tracking)
    print(f"[3/5] Downloading Match Scores (with opponent analysis)...")
    match_count = 0
    for div in divisions:
        page = 1
        while True:
            m_url = f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/matches?per_page=100&page={page}"
            try:
                match_data = safe_request(m_url, headers)
                if not match_data or not match_data.get('data'):
                    break
                
                for m in match_data['data']:
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
                        
                        # Store match details for clutch analysis
                        for team_id in r_ids:
                            match_details.append({
                                'team_ids': r_ids,
                                'team_score': r_score,
                                'opp_score': b_score,
                                'opp_ids': b_ids
                            })
                        for team_id in b_ids:
                            match_details.append({
                                'team_ids': b_ids,
                                'team_score': b_score,
                                'opp_score': r_score,
                                'opp_ids': r_ids
                            })
                        
                        # Update scores
                        for name, s in stats.items():
                            if s['Team_ID'] in r_ids:
                                s['Scores'].append(r_score)
                                s['Opponents_Scores'].append(b_score)
                                # Track wins vs higher/lower ranked
                                for opp_id in b_ids:
                                    if opp_id in team_ranks:
                                        opp_rank = team_ranks[opp_id]
                                        if opp_rank < s['Rank']:  # Opponent ranked higher
                                            if r_score > b_score:
                                                s['Wins_vs_Higher'] += 1
                                            else:
                                                s['Losses_vs_Higher'] += 1
                                        else:  # Opponent ranked lower
                                            if r_score > b_score:
                                                s['Wins_vs_Lower'] += 1
                                            else:
                                                s['Losses_vs_Lower'] += 1
                            
                            if s['Team_ID'] in b_ids:
                                s['Scores'].append(b_score)
                                s['Opponents_Scores'].append(r_score)
                                for opp_id in r_ids:
                                    if opp_id in team_ranks:
                                        opp_rank = team_ranks[opp_id]
                                        if opp_rank < s['Rank']:
                                            if b_score > r_score:
                                                s['Wins_vs_Higher'] += 1
                                            else:
                                                s['Losses_vs_Higher'] += 1
                                        else:
                                            if b_score > r_score:
                                                s['Wins_vs_Lower'] += 1
                                            else:
                                                s['Losses_vs_Lower'] += 1
                
                sys.stdout.write(f"\r   Processed {match_count} matches...")
                sys.stdout.flush()
                page += 1
            except: break
    
    print(f"\n   ✅ Analyzed {match_count} matches")
    
    # Step 4: Historical Wins
    print(f"[4/5] Scanning Season History...")
    count = 0
    for name, s in stats.items():
        count += 1
        sys.stdout.write(f"\r   Scanning {count}/{len(stats)}: {name[:30]}...")
        sys.stdout.flush()
        
        award_data = safe_request(f"https://www.robotevents.com/api/v2/teams/{s['Team_ID']}/awards?season[]={season_id}", headers)
        if award_data:
            for a in award_data.get('data', []):
                title = a.get('title', '')
                if "Champion" in title or "Excellence" in title or "Finalist" in title:
                    s['Past_Wins'] += 1
    
    print(f"\n   ✅ Historical data loaded")
    
    # Step 5: Calculate all metrics
    print(f"\n[5/5] Calculating Enhanced Metrics...")
    print("="*80)
    print("🧮 PHASE 2: ADVANCED ANALYTICS")
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
        
        # Trend calculation
        if len(s['Scores']) >= 5:
            split = max(2, len(s['Scores']) // 2)
            early = s['Scores'][:split]
            late = s['Scores'][-split:]
            trend_delta = round((sum(late)/len(late)) - (sum(early)/len(early)), 1)
            trend = "↑" if trend_delta > 5 else "↓" if trend_delta < -5 else "→"
        else:
            trend_delta = 0
            trend = "→"
        
        # Quality Score
        win_pct = s['WP']
        quality_score = round((avg_pts * 0.6) + (s['SP'] * 0.3) + (win_pct * 10), 1)
        
        # NEW: Ceiling/Floor Analysis
        ceiling_floor = calculate_ceiling_floor(s['Scores'])
        
        # NEW: Clutch Factor
        clutch = calculate_clutch_factor(match_details, s['Team_ID'])
        
        # NEW: Upset Potential
        upset = calculate_upset_potential(
            s['Wins_vs_Higher'], s['Losses_vs_Higher'],
            s['Wins_vs_Lower'], s['Losses_vs_Lower']
        )
        
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
            "Past_Wins": s['Past_Wins'],
            # New metrics
            "Ceiling": ceiling_floor['ceiling'],
            "Floor": ceiling_floor['floor'],
            "Upside": ceiling_floor['upside'],
            "Downside": ceiling_floor['downside'],
            "Volatility_Type": ceiling_floor['volatility_type'],
            "Clutch_Rate": clutch['clutch_rate'],
            "Clutch_Label": clutch['clutch_label'],
            "Close_Matches": clutch['total_close_matches'],
            "Upset_Rate": upset['upset_rate'],
            "Upset_Label": upset['upset_label'],
            "Wins_vs_Higher": upset['wins_vs_higher']
        }
        
        # Save YOUR team's stats
        if my_team and name == my_team:
            my_team_stats = team_data.copy()
            my_team_stats['Scores'] = s['Scores']
            print(f"\n📍 FOUND YOUR TEAM: {my_team}")
            print(f"   Rank: {s['Rank']} | Auto: {s['Auto']} | Avg Pts: {avg_pts}")
            print(f"   Ceiling: {ceiling_floor['ceiling']} | Floor: {ceiling_floor['floor']}")
            print(f"   Clutch: {clutch['clutch_label']} ({clutch['clutch_rate']})")
        
        final_list.append(team_data)
    
    df = pd.DataFrame(final_list)
    
    # ML PREDICTIONS
    print("\n🤖 Running ML Predictions...")
    model = model_data['model']
    feature_cols = model_data['feature_cols']
    
    X = df[feature_cols].fillna(0).copy()
    df['ML_Win_Prob'] = model.predict_proba(X)[:, 1]
    df['ML_Prediction'] = model.predict(X)
    
    # ML Tiers
    df['ML_Tier'] = df['ML_Win_Prob'].apply(
        lambda x: "🎯 TOP PICK" if x >= 0.70 else
                  "✅ STRONG" if x >= 0.50 else
                  "⚠️ RISKY" if x >= 0.30 else
                  "❌ AVOID"
    )
    
    print(f"   ✅ ML predictions complete")
    
    # Traditional categorization
    p75_pts = df['Avg_Pts'].quantile(0.75)
    p75_auto = df['Auto'].quantile(0.75)
    p50_sp = df['SP'].quantile(0.50)
    
    traditional_cats = []
    for idx, row in df.iterrows():
        has_strong_auto = row['Auto'] >= p75_auto
        is_high_scorer = row['Avg_Pts'] >= p75_pts
        is_consistent = row['Std_Dev'] < 12
        is_improving = row['Trend'] == "↑"
        
        if row['Rank'] <= 5 and row['Past_Wins'] >= 1 and is_high_scorer:
            cat = "🏆 ELITE"
        elif row['Rank'] >= 10 and (row['Past_Wins'] > 0 or (is_improving and is_consistent)):
            cat = "🚀 SLEEPER"
        elif row['Rank'] <= 8 and row['Past_Wins'] == 0 and row['SP'] < p50_sp:
            cat = "⚠️ FRAUD"
        elif 11 <= row['Rank'] <= 20 and is_consistent and is_improving:
            cat = "🎯 DARK HORSE"
        elif is_improving and row['Trend_Delta'] >= 8:
            cat = "⚡ PEAKING"
        elif is_high_scorer and not has_strong_auto:
            cat = "🔫 GUNSLINGER"
        elif row['Volatility_Type'] == 'HIGH_UPSIDE':
            cat = "🚀 HIGH CEILING"
        elif row['Clutch_Label'] == '🧊 CLUTCH':
            cat = "🧊 CLUTCH PLAYER"
        else:
            cat = "📊 SOLID"
        
        traditional_cats.append(cat)
    
    df['Traditional_Cat'] = traditional_cats
    
    # Calculate synergy and availability for each team
    if my_team and my_team_stats:
        print("\n🤝 Calculating Push Back synergy scores...")
        synergy_scores = []
        synergy_reasons = []
        availability_labels = []
        availability_scores = []
        partner_scores = []
        
        for idx, row in df.iterrows():
            if row['Team'] == my_team:
                synergy_scores.append(0)
                synergy_reasons.append([])
                availability_labels.append("N/A")
                availability_scores.append(0)
                partner_scores.append(0)
            else:
                # Synergy
                syn = calculate_push_back_synergy(my_team_stats, row.to_dict())
                synergy_scores.append(syn['synergy_score'])
                synergy_reasons.append(syn['reasons'])
                
                # Availability
                avail = predict_availability(row.to_dict(), my_team_stats['Rank'], df)
                availability_labels.append(avail['availability'])
                availability_scores.append(avail['availability_score'])
                
                # Combined Partner Score (weighted)
                p_score = (
                    row['ML_Win_Prob'] * 100 * 0.35 +      # ML weight
                    syn['synergy_score'] * 0.30 +          # Synergy weight
                    (100 / (row['Rank'] + 1)) * 0.15 +     # Rank weight
                    avail['availability_score'] * 50 * 0.20  # Availability weight
                )
                partner_scores.append(round(p_score, 1))
        
        df['Synergy_Score'] = synergy_scores
        df['Synergy_Reasons'] = synergy_reasons
        df['Availability'] = availability_labels
        df['Availability_Score'] = availability_scores
        df['Partner_Score'] = partner_scores
    else:
        df['Synergy_Score'] = 0
        df['Synergy_Reasons'] = [[]] * len(df)
        df['Availability'] = "N/A"
        df['Availability_Score'] = 0
        df['Partner_Score'] = df['ML_Win_Prob'] * 100
    
    # Generate tiered recommendations
    tiers = None
    if my_team and my_team_stats:
        tiers = generate_tiered_recommendations(df, my_team_stats['Rank'], my_team_stats)
    
    return df, my_team_stats, tiers, event_name

# ==============================================================================
# REAL-TIME TRACKING CLASS
# ==============================================================================

class AllianceSelectionTracker:
    """Track alliance selection in real-time"""
    
    def __init__(self, df, my_team, my_rank):
        self.original_df = df.copy()
        self.available_df = df.copy()
        self.my_team = my_team
        self.my_rank = my_rank
        self.selected_teams = []
        self.alliances = {}  # {captain: partner}
    
    def mark_selected(self, team_name, selected_by=None):
        """Mark a team as selected"""
        if team_name in self.selected_teams:
            print(f"   ⚠️ {team_name} already selected")
            return
        
        self.selected_teams.append(team_name)
        self.available_df = self.available_df[self.available_df['Team'] != team_name]
        
        if selected_by:
            self.alliances[selected_by] = team_name
        
        print(f"   ✅ {team_name} marked as selected")
        print(f"   📊 {len(self.available_df)} teams still available")
    
    def get_updated_recommendations(self, top_n=10):
        """Get updated recommendations from remaining teams"""
        pickable = self.available_df[
            (self.available_df['Rank'] > self.my_rank) &
            (~self.available_df['Team'].isin(self.selected_teams))
        ].sort_values('Partner_Score', ascending=False)
        
        return pickable.head(top_n)
    
    def show_status(self):
        """Show current selection status"""
        print("\n" + "="*60)
        print("📋 ALLIANCE SELECTION STATUS")
        print("="*60)
        print(f"Teams selected: {len(self.selected_teams)}")
        print(f"Teams available: {len(self.available_df)}")
        print(f"\nSelected teams: {', '.join(self.selected_teams)}")
        print("\nCurrent alliances:")
        for captain, partner in self.alliances.items():
            print(f"   {captain} + {partner}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("\n" + "▓"*80)
    print("   🤖 IAMJIANGINGIT v5 - ULTIMATE EDITION")
    print("   Enhanced ML + Push Back Synergy + Availability + Real-Time Tracking")
    print("▓"*80)
    
    # Check for API key
    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n⚠️ Please set your API_KEY at the top of the file!")
        sys.exit()
    
    # Load ML model
    if not os.path.exists('alliance_predictor.pkl'):
        print("\n❌ ERROR: alliance_predictor.pkl not found!")
        print("   Run train_model.py first to create the model.")
        sys.exit()
    
    print("\n📂 Loading trained ML model...")
    model_data = joblib.load('alliance_predictor.pkl')
    print("   ✅ Model loaded successfully")
    
    # Get season and analyze
    season_id = get_push_back_id(API_KEY)
    df, my_stats, tiers, event_name = analyze_event_v5(
        TARGET_SKU, API_KEY, season_id, model_data, MY_TEAM
    )
    
    if df is not None and not df.empty:
        # Save full data
        df.to_csv("v5_full_analysis.csv", index=False)
        
        # ======================================================================
        # ENHANCED REPORTS
        # ======================================================================
        
        if MY_TEAM and my_stats and tiers:
            my_rank = my_stats['Rank']
            
            # YOUR TEAM ANALYSIS
            print("\n" + "▓"*80)
            print(f"📍 YOUR TEAM ANALYSIS: {MY_TEAM}")
            print("▓"*80)
            my_row = df[df['Team'] == MY_TEAM].iloc[0]
            print(f"   Rank: {my_rank}")
            print(f"   Record: {my_stats['Record']}")
            print(f"   Auto: {my_stats['Auto']} | Avg Pts: {my_stats['Avg_Pts']}")
            print(f"   Ceiling: {my_stats['Ceiling']} | Floor: {my_stats['Floor']}")
            print(f"   Volatility: {my_stats['Volatility_Type']}")
            print(f"   Clutch: {my_stats['Clutch_Label']} ({my_stats['Clutch_Rate']})")
            print(f"   ML Win Prob: {my_row['ML_Win_Prob']:.1%}")
            print(f"   Category: {my_row['Traditional_Cat']}")
            
            # TIERED RECOMMENDATIONS
            print("\n" + "▓"*80)
            print(f"🎯 TIERED RECOMMENDATIONS FOR {MY_TEAM}")
            print("▓"*80)
            
            # Tier A
            print("\n" + "="*60)
            print("🅰️  TIER A - BEST CASE (Your top picks)")
            print("="*60)
            if not tiers['tier_a'].empty:
                for _, t in tiers['tier_a'].iterrows():
                    avail = t.get('Availability', 'N/A')
                    print(f"   {t['Team']:12} | Rank {t['Rank']:2} | ML: {t['ML_Win_Prob']:.0%} | Synergy: {t['Synergy_Score']:+.0f} | {avail}")
            
            # Tier B
            print("\n" + "="*60)
            print("🅱️  TIER B - REALISTIC (If top picks are gone)")
            print("="*60)
            if not tiers['tier_b'].empty:
                for _, t in tiers['tier_b'].iterrows():
                    avail = t.get('Availability', 'N/A')
                    print(f"   {t['Team']:12} | Rank {t['Rank']:2} | ML: {t['ML_Win_Prob']:.0%} | Synergy: {t['Synergy_Score']:+.0f} | {avail}")
            
            # Tier C
            print("\n" + "="*60)
            print("🆘 TIER C - EMERGENCY (Sleepers & Dark Horses)")
            print("="*60)
            if not tiers['tier_c'].empty:
                for _, t in tiers['tier_c'].iterrows():
                    print(f"   {t['Team']:12} | Rank {t['Rank']:2} | ML: {t['ML_Win_Prob']:.0%} | {t['Traditional_Cat']}")
            else:
                print("   No emergency picks identified")
            
            # Safe Picks
            print("\n" + "="*60)
            print("🛡️  SAFE PICKS (Consistent, low variance)")
            print("="*60)
            if not tiers['tier_safe'].empty:
                for _, t in tiers['tier_safe'].iterrows():
                    print(f"   {t['Team']:12} | Rank {t['Rank']:2} | Std Dev: {t['Std_Dev']:.1f} | Floor: {t['Floor']:.0f}")
            
            # Boom Picks
            print("\n" + "="*60)
            print("💥 BOOM PICKS (High ceiling for aggressive play)")
            print("="*60)
            if not tiers['tier_boom'].empty:
                for _, t in tiers['tier_boom'].iterrows():
                    print(f"   {t['Team']:12} | Rank {t['Rank']:2} | Ceiling: {t['Ceiling']:.0f} | Upside: +{t['Upside']:.0f}")
            
            # Synergy breakdown for top pick
            print("\n" + "="*60)
            print("🔍 SYNERGY BREAKDOWN - TOP RECOMMENDATION")
            print("="*60)
            if not tiers['tier_a'].empty:
                top_pick = tiers['tier_a'].iloc[0]
                print(f"   Team: {top_pick['Team']}")
                print(f"   Partner Score: {top_pick['Partner_Score']:.1f}")
                print(f"   Synergy Reasons:")
                for reason in top_pick['Synergy_Reasons']:
                    print(f"      • {reason}")
        
        # FRAUD WATCH
        print("\n" + "="*60)
        print("⚠️  FRAUD WATCH (High rank but low ML)")
        print("="*60)
        frauds = df[(df['ML_Win_Prob'] < 0.40) & (df['Rank'] <= 8)]
        if not frauds.empty:
            for _, t in frauds.iterrows():
                print(f"   {t['Team']:12} | Rank {t['Rank']:2} | ML: {t['ML_Win_Prob']:.0%} | {t['Clutch_Label']}")
        else:
            print("   ✅ No frauds detected in top 8!")
        
        # CLUTCH PLAYERS
        print("\n" + "="*60)
        print("🧊 CLUTCH PLAYERS (Win close matches)")
        print("="*60)
        clutch_players = df[df['Clutch_Label'] == '🧊 CLUTCH'].sort_values('Clutch_Rate', ascending=False)
        if not clutch_players.empty:
            for _, t in clutch_players.head(10).iterrows():
                print(f"   {t['Team']:12} | Rank {t['Rank']:2} | Clutch Rate: {t['Clutch_Rate']:.0%} | Close W: {t['Close_Matches']}")
        
        # GIANT KILLERS
        print("\n" + "="*60)
        print("🔥 GIANT KILLERS (Beat higher-ranked teams)")
        print("="*60)
        giant_killers = df[df['Upset_Label'] == '🔥 GIANT KILLER'].sort_values('Upset_Rate', ascending=False)
        if not giant_killers.empty:
            for _, t in giant_killers.head(10).iterrows():
                print(f"   {t['Team']:12} | Rank {t['Rank']:2} | Upset Rate: {t['Upset_Rate']:.0%} | Wins vs Higher: {t['Wins_vs_Higher']}")
        
        # STATISTICS
        print("\n" + "="*60)
        print("📊 EVENT STATISTICS")
        print("="*60)
        print(f"   Event: {event_name}")
        print(f"   Total Teams: {len(df)}")
        print(f"   ML Top Picks (70%+): {len(df[df['ML_Win_Prob'] >= 0.70])}")
        print(f"   Clutch Players: {len(clutch_players)}")
        print(f"   Giant Killers: {len(giant_killers)}")
        print(f"   High Ceiling Teams: {len(df[df['Volatility_Type'] == 'HIGH_UPSIDE'])}")
        
        print("\n" + "="*60)
        print("✅ FILES SAVED:")
        print("="*60)
        print("   • v5_full_analysis.csv - Complete analysis")
        
        # Initialize real-time tracker
        print("\n" + "="*60)
        print("🔴 REAL-TIME TRACKING AVAILABLE")
        print("="*60)
        print("   To use during alliance selection, run:")
        print("   >>> tracker = AllianceSelectionTracker(df, MY_TEAM, my_rank)")
        print("   >>> tracker.mark_selected('1234A', selected_by='5678B')")
        print("   >>> tracker.get_updated_recommendations()")
        print("="*60)
