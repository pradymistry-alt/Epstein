import os
import joblib
import pandas as pd
import numpy as np
import requests
import json
import traceback
import time
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from sklearn.ensemble import RandomForestClassifier

# --- CONFIGURATION ---
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"
MODEL_FILE = 'alliance_predictor.pkl'

app = Flask(__name__)
CORS(app)

# ==============================================================================
#  1. DEEP MINER
# ==============================================================================
def find_training_events():
    print("\n🌍 DEEP MINER: Searching for 50+ Large 'Push Back' Tournaments...")
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    
    events = [
        "RE-V5RC-25-0179", "RE-V5RC-25-1516", "RE-V5RC-25-9998", 
        "RE-V5RC-25-9941", "RE-V5RC-25-2145", "RE-V5RC-25-9915", "RE-V5RC-25-9994"
    ]
    
    season_id = 200 
    try:
        r = requests.get("https://www.robotevents.com/api/v2/seasons?program[]=1", headers=headers)
        for s in r.json().get('data', []):
            if "Push Back" in s['name']: season_id = s['id']
    except: pass

    page = 1
    while len(events) < 55 and page < 20:
        url = f"https://www.robotevents.com/api/v2/events?season[]={season_id}&end=2025-12-18&per_page=50&page={page}"
        try:
            r = requests.get(url, headers=headers)
            data = r.json().get('data', [])
            if not data: break
            
            print(f"   🔎 Page {page}: Found {len(data)} events... (Total Valid: {len(events)})")
            for e in data:
                if len(events) >= 55: break
                if ("Tournament" in e['event_type'] or "Signature" in e['event_type']) and e['sku'] not in events:
                    try:
                        tr = requests.get(f"https://www.robotevents.com/api/v2/events/{e['id']}/teams?per_page=1", headers=headers)
                        if tr.json().get('meta', {}).get('total', 0) >= 40:
                            events.append(e['sku'])
                    except: pass
            page += 1
        except: break
    return events

# ==============================================================================
#  2. TRAINING ENGINE
# ==============================================================================
def train_model():
    if os.path.exists(MODEL_FILE): return
    events = find_training_events()
    print("🧠 TRAINING: Building the Ultimate Brain...")
    
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    all_dfs = []
    
    for i, sku in enumerate(events):
        try:
            r = requests.get(f"https://www.robotevents.com/api/v2/events?sku={sku}", headers=headers)
            if not r.json().get('data'): continue
            eid = r.json()['data'][0]['id']
            divs = r.json()['data'][0]['divisions']
            
            stats = {}
            for d in divs:
                rr = requests.get(f"https://www.robotevents.com/api/v2/events/{eid}/divisions/{d['id']}/rankings?per_page=250", headers=headers)
                for t in rr.json().get('data', []):
                    stats[t['team']['id']] = {'Rank': t['rank'], 'Auto': t['ap'], 'SP': t['sp'], 'Scores': []}
                    
            for d in divs:
                mr = requests.get(f"https://www.robotevents.com/api/v2/events/{eid}/divisions/{d['id']}/matches?per_page=250", headers=headers)
                for m in mr.json().get('data', []):
                    alliances = m.get('alliances', [])
                    adict = {}
                    if isinstance(alliances, list):
                        for a in alliances: adict[a.get('color')] = a
                    else: adict = alliances
                    
                    for color in ['red', 'blue']:
                        score = adict.get(color, {}).get('score', 0)
                        teams = adict.get(color, {}).get('teams', [])
                        for t in teams:
                            tid = t['team']['id'] if 'team' in t else t.get('id')
                            if tid in stats: stats[tid]['Scores'].append(score)

            ar = requests.get(f"https://www.robotevents.com/api/v2/events/{eid}/awards", headers=headers)
            winners = set()
            for a in ar.json().get('data', []):
                if "Champion" in a['title'] or "Excellence" in a['title']:
                    for w in a.get('teamWinners', []): winners.add(w.get('team', {}).get('id'))

            rows = []
            for tid, s in stats.items():
                if not s['Scores']: continue
                rows.append({
                    'Rank': s['Rank'], 'Auto': s['Auto'], 'SP': s['SP'],
                    'Avg_Pts': np.mean(s['Scores']), 'Std_Dev': np.std(s['Scores']),
                    'Was_Successful': 1 if tid in winners else 0
                })
            
            if rows: 
                all_dfs.append(pd.DataFrame(rows))
                if i % 5 == 0: print(f"   ... Processed {i}/{len(events)}")
                
        except: pass

    if all_dfs:
        full_data = pd.concat(all_dfs).fillna(0)
        features = ['Rank', 'Auto', 'SP', 'Avg_Pts', 'Std_Dev']
        model = RandomForestClassifier(n_estimators=150, class_weight='balanced', max_depth=8)
        model.fit(full_data[features], full_data['Was_Successful'])
        joblib.dump({'model': model, 'feature_cols': features}, MODEL_FILE)
        print("✅ Brain Trained Successfully!")
    else:
        train_synthetic()

def train_synthetic():
    print("⚠️ Using Synthetic Training.")
    data, labels = [], []
    for _ in range(5000):
        data.append([np.random.randint(1,100), np.random.randint(0,40), np.random.randint(0,200), 
                     np.random.randint(20,120), np.random.randint(5,40)])
        labels.append(np.random.randint(0,2))
    model = RandomForestClassifier()
    model.fit(pd.DataFrame(data, columns=['Rank','Auto','SP','Avg_Pts','Std_Dev']), labels)
    joblib.dump({'model': model, 'feature_cols': ['Rank','Auto','SP','Avg_Pts','Std_Dev']}, MODEL_FILE)

# ==============================================================================
# 3. ANALYSIS LOGIC (Balanced Awards)
# ==============================================================================
def analyze_event(sku, api_key, my_team):
    train_model()
    model_data = joblib.load(MODEL_FILE)
    model = model_data['model']
    
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    try:
        r = requests.get(f"https://www.robotevents.com/api/v2/events?sku={sku}&include=divisions", headers=headers)
        data = r.json().get('data', [])
        if not data: return None, None
        eid = data[0]['id']
        divs = data[0].get('divisions', [{'id': 1}])
    except: return None, None

    stats = {}
    
    # 1. Rankings
    for d in divs:
        page = 1
        while True:
            try:
                url = f"https://www.robotevents.com/api/v2/events/{eid}/divisions/{d['id']}/rankings?page={page}&per_page=250"
                r = requests.get(url, headers=headers)
                d_data = r.json().get('data', [])
                if not d_data: break
                for t in d_data:
                    stats[t['team']['name']] = {
                        'Rank': t['rank'], 'Auto': t['ap'], 'SP': t['sp'], 'WP': t['wp'],
                        'Record': f"{t['wins']}-{t['losses']}-{t['ties']}",
                        'Scores': [], 'Close_Wins': 0, 'Close_Matches': 0,
                        'Wins_Higher': 0, 'Losses_Higher': 0, 'Blowout_Wins': 0,
                        'Awards': [] 
                    }
                page += 1
            except: break

    # 2. Matches
    for d in divs:
        page = 1
        while True:
            try:
                url = f"https://www.robotevents.com/api/v2/events/{eid}/divisions/{d['id']}/matches?page={page}&per_page=250"
                r = requests.get(url, headers=headers)
                d_data = r.json().get('data', [])
                if not d_data: break
                
                for m in d_data:
                    alliances = m.get('alliances', [])
                    adict = {}
                    if isinstance(alliances, list):
                        for a in alliances: adict[a.get('color')] = a
                    else: adict = alliances
                    
                    r_score = adict.get('red', {}).get('score', 0)
                    b_score = adict.get('blue', {}).get('score', 0)
                    
                    if not isinstance(r_score, (int, float)) or not isinstance(b_score, (int, float)): continue
                    
                    margin = abs(r_score - b_score)
                    is_close = margin <= 15
                    is_blowout = margin >= 50
                    
                    for color in ['red', 'blue']:
                        score = r_score if color == 'red' else b_score
                        opp_score = b_score if color == 'red' else r_score
                        won = score > opp_score
                        teams = adict.get(color, {}).get('teams', [])
                        opp_teams = adict.get('blue' if color == 'red' else 'red', {}).get('teams', [])
                        
                        for t in teams:
                            tname = t.get('team', {}).get('name') if 'team' in t else t.get('name')
                            if tname in stats:
                                stats[tname]['Scores'].append(score)
                                if is_close:
                                    stats[tname]['Close_Matches'] += 1
                                    if won: stats[tname]['Close_Wins'] += 1
                                if is_blowout and won:
                                    stats[tname]['Blowout_Wins'] += 1
                                
                                my_rank = stats[tname]['Rank']
                                for opp in opp_teams:
                                    oname = opp.get('team', {}).get('name') if 'team' in opp else opp.get('name')
                                    if oname in stats:
                                        opp_rank = stats[oname]['Rank']
                                        if opp_rank < my_rank: 
                                            if won: stats[tname]['Wins_Higher'] += 1
                                            else: stats[tname]['Losses_Higher'] += 1
                page += 1
            except: break

    # 3. Awards Check
    try:
        ar = requests.get(f"https://www.robotevents.com/api/v2/events/{eid}/awards", headers=headers)
        for a in ar.json().get('data', []):
            title = a.get('title', '')
            tag = ""
            if "Champion" in title: tag = "TC"
            elif "Finalist" in title: tag = "TF"
            elif "Excellence" in title: tag = "EX"
            
            if tag:
                for w in a.get('teamWinners', []): 
                    tname = w.get('team', {}).get('name')
                    if tname in stats:
                        stats[tname]['Awards'].append(tag)
    except: pass

    processed = []
    my_stats = stats.get(my_team, {'Rank': 999, 'Auto': 0, 'Avg_Pts': 0, 'Std_Dev': 0, 'Scores': []})
    if 'Avg_Pts' not in my_stats: 
        my_stats['Avg_Pts'] = np.mean(my_stats['Scores']) if my_stats['Scores'] else 0
        my_stats['Std_Dev'] = np.std(my_stats['Scores']) if my_stats['Scores'] else 0

    all_sp = [s['SP'] for s in stats.values() if s['SP'] > 0]
    global_avg_sp = np.mean(all_sp) if all_sp else 10

    for name, s in stats.items():
        if not s['Scores']: continue
        avg_score = np.mean(s['Scores'])
        std_dev = np.std(s['Scores'])
        
        ceil = np.percentile(s['Scores'], 90) if len(s['Scores']) > 2 else avg_score
        floor = np.percentile(s['Scores'], 10) if len(s['Scores']) > 2 else avg_score
        upside = ceil - avg_score
        
        clutch_rate = s['Close_Wins'] / s['Close_Matches'] if s['Close_Matches'] > 0 else 0.5
        
        # Base Quality
        quality = (avg_score * 0.6) + (s['SP'] * 0.3)
        if s['SP'] < (global_avg_sp * 0.6): quality *= 0.85 # SOS Tax
        
        # AI Prediction
        try:
            prob = model.predict_proba([[s['Rank'], s['Auto'], s['SP'], avg_score, std_dev]])[0][1]
        except: prob = 0.5
        
        syn = 0
        reasons = []
        if my_stats['Auto'] + s['Auto'] >= 12: 
            syn += 20
            reasons.append("Elite Auto")
        elif s['Auto'] >= 6 and my_stats['Auto'] < 6:
            syn += 15
            reasons.append("Covers Auto Weakness")
        if std_dev < 10: 
            syn += 10
            reasons.append("Consistent")
        if my_stats['Avg_Pts'] < 30 and avg_score > 40:
            syn += 15
            reasons.append("Scoring Carry")
            
        clutch_label = "Normal"
        has_tc = "TC" in s['Awards']
        has_ex = "EX" in s['Awards']
        has_tf = "TF" in s['Awards']
        
        # --- BALANCED AWARDS LOGIC ---
        # No more 95% overrides. Just bonus points.
        award_bonus = 0
        if has_tc:
            clutch_label = "🏆 CHAMPION"
            award_bonus = 20
            prob += 0.10 
        elif has_ex:
            clutch_label = "⭐ EXCELLENCE"
            award_bonus = 15
            prob += 0.08
        elif has_tf:
            clutch_label = "🥈 FINALIST"
            award_bonus = 10
            prob += 0.05
        
        # Performance Labels
        if s['Blowout_Wins'] > 2:
            if not has_tc: clutch_label = "🔥 DOMINANT"
        elif clutch_rate > 0.7 and s['Close_Matches'] > 2:
            if not has_tc: clutch_label = "🧊 CLUTCH"
        elif s['Wins_Higher'] > 2:
            if not has_tc: clutch_label = "⚡ GIANT KILLER"
        
        # Apply Bonus
        quality += award_bonus
        
        vol_label = "Balanced"
        if upside > 25: vol_label = "🚀 HIGH CEILING"
        elif std_dev > 25: vol_label = "⚠️ VOLATILE"
        elif std_dev < 10: vol_label = "🗿 ROCK SOLID"
        
        avail = "Available"
        if s['Rank'] < my_stats['Rank']: avail = "Likely Gone"
        elif prob > 0.6 and s['Rank'] > 15: avail = "Steal!"

        is_fraud = False
        if not (has_tc or has_ex or has_tf): 
            if s['Rank'] <= 10 and s['Blowout_Wins'] < 1:
                if clutch_rate < 0.3 and s['Close_Matches'] > 1:
                    is_fraud = True
                    clutch_label = "⚠️ FRAUD (Choker)"
                elif prob < 0.4:
                    is_fraud = True
                    clutch_label = "⚠️ FRAUD (Paper Tiger)"

        processed.append({
            'Team': name, 'Rank': s['Rank'], 'Auto': f"{s['Auto']} AP",
            'Quality_Score': int(quality),
            'Avg_Pts': round(avg_score, 1),
            'ML_Win_Prob': min(float(prob), 0.99), # Cap at 99%
            'Synergy_Score': syn, 'Synergy_Reasons': reasons,
            'Clutch_Label': clutch_label, 'Traditional_Cat': vol_label,
            'Availability': avail,
            'Ceiling': int(ceil), 'Floor': int(floor), 'Upside': int(upside),
            'Is_Fraud': is_fraud
        })
        
    for p in processed:
        p['Partner_Score'] = (p['ML_Win_Prob']*100) + p['Synergy_Score'] + (100/(p['Rank']+1))
        
    processed.sort(key=lambda x: x['Partner_Score'], reverse=True)
    
    return processed, my_stats

# ==============================================================================
#  4. ROUTES
# ==============================================================================
@app.route('/')
def index():
    return Response(open('index.html', encoding='utf-8').read(), mimetype='text/html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    req = request.json
    api_key, sku, my_team = req.get('apiKey'), req.get('eventSku'), req.get('myTeam')
    
    data, my_stats = analyze_event(sku, api_key, my_team)
    if not data: return jsonify({'error': 'No data'}), 404
    
    pickable = [d for d in data if d['Rank'] > my_stats['Rank']]
    frauds = [d for d in data if d['Is_Fraud']]
    
    return jsonify({
        'eventName': sku,
        'myRank': my_stats['Rank'],
        'myTeamData': {'Rank': my_stats['Rank'], 'Avg_Pts': round(my_stats['Avg_Pts'],1), 'Auto': my_stats['Auto']},
        'tierA': pickable[:8],
        'tierB': pickable[8:16],
        'tierC': pickable[16:24],
        'tierSafe': [d for d in pickable if "ROCK SOLID" in d['Traditional_Cat']][:5],
        'tierBoom': [d for d in pickable if "HIGH CEILING" in d['Traditional_Cat']][:5],
        'frauds': frauds,
        'recommended': pickable[0] if pickable else None,
        'allPickable': pickable
    })

if __name__ == '__main__':
    print("🚀 Server starting...")
    app.run(debug=True)