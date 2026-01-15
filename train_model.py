import requests
import pandas as pd
import numpy as np
import sys
import joblib
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report
import warnings

warnings.filterwarnings('ignore')

print("\n✅ HYBRID TRAINING - Your Events + Auto-Discovery\n")

# ==============================================================================
#  CONFIGURATION - CUSTOMIZE THIS!
# ==============================================================================

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"

# YOUR SPECIFIC EVENTS (Always included - These are your region/important events)
MY_EVENTS = [
    "RE-V5RC-25-0179", "RE-V5RC-25-9994", "RE-V5RC-25-9941", "RE-V5RC-25-1516", "RE-V5RC-25-9998", "RE-V5RC-25-0555", "RE-V5RC-25-9933", "RE-V5RC-25-0153", "RE-V5RC-25-9915", "RE-V5RC-25-9997", "RE-V5RC-25-2145", "RE-V5RC-25-0094", "RE-V5RC-25-0024", "RE-V5RC-25-9926", "RE-V5RC-25-2110", "RE-V5RC-25-1749"
    # Add more of YOUR events...
]

# AUTO-DISCOVERY SETTINGS
AUTO_DISCOVER = True  # Set to False to only use MY_EVENTS
ADDITIONAL_EVENTS_NEEDED = 30  # How many extra events to find (0 = just use MY_EVENTS)

# FILTERING OPTIONS (Make auto-discovery smarter)
FILTERS = {
    "regions": [],  # e.g., ["Massachusetts", "New England", "California"] - Empty = all regions
    "min_teams": 40,  # Skip small events (less realistic data)
    "event_types": ["Tournament", "Signature"],  # Skip scrimmages
    "start_date": "2025-09-01",  # Only events after this date
    "end_date": "2025-12-31"  # Only events before this date
}

# ==============================================================================
# SAFE REQUEST HANDLER
# ==============================================================================
def safe_request(url, headers, delay=0.4):
    """Make API request with rate limit protection"""
    time.sleep(delay)
    
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            
            if r.status_code == 429:
                wait = (attempt + 1) * 5
                time.sleep(wait)
                continue
            
            if r.status_code >= 500:
                return None
                
            return r.json()
            
        except Exception:
            if attempt == 2:
                return None
            time.sleep(2)
    
    return None

# ==============================================================================
# AUTO-DISCOVERY ENGINE
# ==============================================================================
def discover_additional_events(api_key, target_count, filters, exclude_skus):
    """
    Smart event discovery based on filters
    Returns list of event SKUs
    """
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    print("\n" + "="*80)
    print("🔍 AUTO-DISCOVERING ADDITIONAL TRAINING EVENTS")
    print("="*80)
    
    # Get season ID
    season_data = safe_request("https://www.robotevents.com/api/v2/seasons?program[]=1", headers)
    season_id = None
    
    if season_data:
        for season in season_data['data']:
            if "Push Back" in season['name']:
                season_id = season['id']
                print(f"   Season: {season['name']} (ID: {season_id})")
                break
    
    if not season_id:
        print("   ⚠️ Could not find Push Back season")
        return []
    
    # Search for events
    discovered = []
    page = 1
    max_pages = 10  # Safety limit to avoid infinite loop
    
    print(f"   Target: {target_count} additional events")
    print(f"   Filters: min_teams={filters['min_teams']}, types={filters['event_types']}")
    
    while len(discovered) < target_count and page <= max_pages:
        # Build query parameters
        params = [
            f"season[]={season_id}",
            f"per_page=50",
            f"page={page}"
        ]
        
        # Add date filters
        if filters.get('start_date'):
            params.append(f"start={filters['start_date']}")
        if filters.get('end_date'):
            params.append(f"end={filters['end_date']}")
        
        url = f"https://www.robotevents.com/api/v2/events?{'&'.join(params)}"
        event_data = safe_request(url, headers, delay=0.6)
        
        if not event_data or not event_data.get('data'):
            break
        
        for event in event_data['data']:
            if len(discovered) >= target_count:
                break
            
            sku = event['sku']
            name = event['name']
            
            # Skip if already in our list
            if sku in exclude_skus or sku in discovered:
                continue
            
            # Apply filters
            # Check event type
            if filters.get('event_types'):
                if not any(etype in name for etype in filters['event_types']):
                    continue
            
            # Check region
            if filters.get('regions'):
                location = f"{event.get('location', {}).get('city', '')} {event.get('location', {}).get('region', '')}"
                if not any(region.lower() in location.lower() for region in filters['regions']):
                    continue
            
            # Quick check: Does it have teams? (Avoid empty events)
            teams_url = f"https://www.robotevents.com/api/v2/events/{event['id']}/teams?per_page=1"
            teams_check = safe_request(teams_url, headers, delay=0.3)
            
            if teams_check and teams_check.get('meta', {}).get('total', 0) >= filters['min_teams']:
                discovered.append(sku)
                print(f"   ✅ Found: {name} ({sku}) - {teams_check['meta']['total']} teams")
        
        page += 1
        sys.stdout.write(f"\r   Scanning page {page}... Found {len(discovered)}/{target_count}")
        sys.stdout.flush()
    
    print(f"\n   🎉 Discovered {len(discovered)} events")
    return discovered

# ==============================================================================
# AWARD-BASED SUCCESS DETECTION
# ==============================================================================
def get_successful_teams_from_awards(event_id, headers):
    """Get teams that won major awards at this event"""
    successful_teams = set()
    
    SUCCESS_AWARDS = [
        "Tournament Champion",
        "Tournament Finalist", 
        "Excellence Award",
        "Robot Skills Champion"
    ]
    
    url = f"https://www.robotevents.com/api/v2/events/{event_id}/awards"
    awards_data = safe_request(url, headers, delay=0.5)
    
    if not awards_data:
        return successful_teams
    
    for award in awards_data.get('data', []):
        title = award.get('title', '')
        
        if any(success_word in title for success_word in SUCCESS_AWARDS):
            for recipient in award.get('teamWinners', []):
                if 'team' in recipient and 'id' in recipient['team']:
                    successful_teams.add(recipient['team']['id'])
    
    return successful_teams

def get_top_performers(stats_dict, top_n=8):
    """Fallback: Use top N ranked teams as successful"""
    sorted_teams = sorted(stats_dict.items(), key=lambda x: x[1]['Rank'])
    return {s['Team_ID'] for name, s in sorted_teams[:top_n]}

# ==============================================================================
# DATA COLLECTION
# ==============================================================================
def collect_event_data(sku, api_key):
    """Collect training data from one event"""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    print(f"\n📊 Processing: {sku}")
    
    # Connect to event
    event_json = safe_request(f"https://www.robotevents.com/api/v2/events?sku={sku}&include=divisions", headers)
    
    if not event_json or not event_json.get('data'):
        print("   ❌ Skipped (no data)")
        return None
    
    event_data = event_json['data'][0]
    event_id = event_data['id']
    divisions = event_data.get('divisions', [])
    print(f"   Connected: {event_data['name']}")
    
    stats = {}
    
    # RANKINGS
    for div in divisions:
        page = 1
        while True:
            url = f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/rankings?per_page=100&page={page}"
            data = safe_request(url, headers)
            
            if not data or not data.get('data'):
                break
            
            for t in data['data']:
                name = t['team']['name']
                t_id = t['team']['id']
                total = t['wins'] + t['losses'] + t['ties']
                
                if total == 0:
                    continue
                
                stats[name] = {
                    "Team_ID": t_id,
                    "Rank": t['rank'],
                    "Auto": round(t['ap'] / total, 2),
                    "SP": round(t['sp'] / total, 1),
                    "Scores": [],
                    "Skills": 0
                }
            
            page += 1
    
    # SKILLS
    page = 1
    while True:
        url = f"https://www.robotevents.com/api/v2/events/{event_id}/skills?per_page=100&page={page}"
        data = safe_request(url, headers)
        
        if not data or not data.get('data'):
            break
        
        for t in data['data']:
            name = t['team']['name']
            if name in stats:
                stats[name]['Skills'] = max(stats[name]['Skills'], t['score'])
        
        page += 1
    
    # MATCH SCORES
    for div in divisions:
        page = 1
        while True:
            url = f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/matches?per_page=100&page={page}"
            data = safe_request(url, headers)
            
            if not data or not data.get('data'):
                break
            
            for match in data['data']:
                alliances = match.get('alliances', [])
                
                if isinstance(alliances, list):
                    for alliance in alliances:
                        score = alliance.get('score', 0)
                        for team_info in alliance.get('teams', []):
                            if 'team' in team_info and 'id' in team_info['team']:
                                t_id = team_info['team']['id']
                                for s in stats.values():
                                    if s['Team_ID'] == t_id:
                                        s['Scores'].append(score)
            
            page += 1
    
    # DETERMINE SUCCESS
    print(f"   🏆 Checking awards...")
    successful_teams = get_successful_teams_from_awards(event_id, headers)
    
    if len(successful_teams) == 0:
        print(f"   ⚠️ No awards - using Top 8")
        successful_teams = get_top_performers(stats, top_n=8)
    
    # BUILD DATAFRAME
    rows = []
    for name, s in stats.items():
        if len(s['Scores']) == 0:
            continue
        
        avg_pts = round(sum(s['Scores']) / len(s['Scores']), 1)
        std_dev = round(np.std(s['Scores']), 1) if len(s['Scores']) > 2 else 0
        
        trend_delta = 0
        if len(s['Scores']) >= 4:
            mid = len(s['Scores']) // 2
            early = np.mean(s['Scores'][:mid])
            late = np.mean(s['Scores'][mid:])
            trend_delta = round(late - early, 1)
        
        rows.append({
            "Rank": s['Rank'],
            "Auto": s['Auto'],
            "SP": s['SP'],
            "Avg_Pts": avg_pts,
            "Std_Dev": std_dev,
            "Trend_Delta": trend_delta,
            "Skills": s['Skills'],
            "Was_Successful": 1 if s['Team_ID'] in successful_teams else 0
        })
    
    success_count = sum(1 for r in rows if r['Was_Successful'] == 1)
    print(f"   ✅ {len(rows)} teams | {success_count} successful")
    
    return pd.DataFrame(rows)

# ==============================================================================
# TRAIN MODEL
# ==============================================================================
def train_alliance_predictor(api_key):
    print("\n" + "="*80)
    print("🤖 ML TRAINING - HYBRID SYSTEM")
    print("="*80)
    
    # Build final event list
    final_events = list(MY_EVENTS)  # Start with your events
    
    print(f"\n📋 YOUR EVENTS: {len(MY_EVENTS)}")
    for sku in MY_EVENTS:
        print(f"   - {sku}")
    
    # Auto-discover additional events if needed
    if AUTO_DISCOVER and ADDITIONAL_EVENTS_NEEDED > 0:
        discovered = discover_additional_events(
            api_key, 
            ADDITIONAL_EVENTS_NEEDED, 
            FILTERS, 
            exclude_skus=set(MY_EVENTS)
        )
        final_events.extend(discovered)
    
    print(f"\n📊 TOTAL EVENTS FOR TRAINING: {len(final_events)}")
    
    # Collect data from all events
    all_dfs = []
    for i, sku in enumerate(final_events, 1):
        print(f"\n[{i}/{len(final_events)}]", end=" ")
        df = collect_event_data(sku, api_key)
        if df is not None and not df.empty:
            all_dfs.append(df)
    
    if not all_dfs:
        print("\n❌ No data collected.")
        return
    
    # Combine all data
    full_data = pd.concat(all_dfs, ignore_index=True)
    full_data = full_data.fillna(0)
    full_data.to_csv("training_data_raw.csv", index=False)
    
    print("\n" + "="*80)
    print("📊 TRAINING DATA SUMMARY")
    print("="*80)
    print(f"   Events used: {len(all_dfs)}")
    print(f"   Total teams: {len(full_data)}")
    print(f"   Successful: {full_data['Was_Successful'].sum()}")
    print(f"   Not successful: {len(full_data) - full_data['Was_Successful'].sum()}")
    print(f"   Success rate: {full_data['Was_Successful'].mean():.1%}")
    
    # Check balance
    if len(full_data['Was_Successful'].unique()) < 2:
        print("\n⚠️ WARNING: Only one class - adding synthetic data")
        fake_row = full_data.iloc[0].copy()
        fake_row['Was_Successful'] = 1 - fake_row['Was_Successful']
        full_data = pd.concat([full_data, pd.DataFrame([fake_row])], ignore_index=True)
    
    # Train model
    feature_cols = ['Rank', 'Auto', 'SP', 'Avg_Pts', 'Std_Dev', 'Trend_Delta', 'Skills']
    X = full_data[feature_cols]
    y = full_data['Was_Successful']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print("\n🌲 Training Random Forest...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=5,
        class_weight='balanced',
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # Evaluate
    train_acc = model.score(X_train, y_train)
    test_acc = model.score(X_test, y_test)
    
    print(f"   Training Accuracy: {train_acc:.2%}")
    print(f"   Test Accuracy: {test_acc:.2%}")
    
    cv_scores = cross_val_score(model, X, y, cv=min(5, len(y)))
    print(f"   Cross-Val Accuracy: {cv_scores.mean():.2%} (+/- {cv_scores.std():.2%})")
    
    # Classification report
    y_pred = model.predict(X_test)
    print("\n📊 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Not Successful', 'Successful']))
    
    # Feature importance
    print("\n🔍 Feature Importance:")
    importances = pd.DataFrame({
        'Feature': feature_cols,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    print(importances.to_string(index=False))
    
    # Save model
    model_data = {
        'model': model,
        'feature_cols': feature_cols
    }
    joblib.dump(model_data, 'alliance_predictor.pkl')
    
    print("\n" + "="*80)
    print("🎉 TRAINING COMPLETE!")
    print("="*80)
    print("✅ Model saved as 'alliance_predictor.pkl'")
    print("✅ Training data saved as 'training_data_raw.csv'")
    print(f"✅ Model trained on {len(all_dfs)} events, {len(full_data)} teams")
    print("="*80)
    
    return model

# ==============================================================================
# RUN TRAINING
# ==============================================================================
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("\n" + "▓"*80)
    print("   🧠 HYBRID ML TRAINING SYSTEM")
    print("   Your Events + Smart Auto-Discovery")
    print("▓"*80)
    
    model = train_alliance_predictor(API_KEY)
    
    print("\n✅ Ready! Run 'python iamjiangingit_v4.py' at your next comp\n")