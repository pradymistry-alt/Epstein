from flask import Flask, request, Response, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VEX Scout v4</title>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .card { background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; padding: 20px; }
        .title { font-size: 28px; font-weight: bold; margin-bottom: 10px; }
        .btn { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-weight: 500; margin: 5px; background: #3b82f6; color: white; }
        .btn:hover { background: #2563eb; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 6px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f9fafb; font-weight: 600; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .badge-green { background: #d1fae5; color: #065f46; }
        .badge-blue { background: #dbeafe; color: #1e40af; }
        .badge-yellow { background: #fef3c7; color: #92400e; }
        .badge-red { background: #fee2e2; color: #991b1b; }
        .badge-purple { background: #e9d5ff; color: #6b21a8; }
        .status { padding: 10px; margin: 10px 0; border-radius: 6px; text-align: center; }
        .status-success { background: #d1fae5; color: #065f46; }
        .status-error { background: #fee2e2; color: #991b1b; }
        .tabs { display: flex; border-bottom: 2px solid #eee; margin-bottom: 20px; }
        .tab { padding: 12px 24px; border: none; background: none; cursor: pointer; border-bottom: 2px solid transparent; }
        .tab.active { border-bottom-color: #3b82f6; color: #3b82f6; }
    </style>
</head>
<body>
    <div id="root"></div>
    <script type="text/babel">
        const { useState } = React;
        
        const App = () => {
            const [tab, setTab] = useState('settings');
            const [apiKey, setApiKey] = useState('');
            const [sku, setSku] = useState('');
            const [myTeam, setMyTeam] = useState('8568A');
            const [loading, setLoading] = useState(false);
            const [status, setStatus] = useState('Ready');
            const [data, setData] = useState(null);
            
            const analyze = async () => {
                if (!apiKey || !sku) { setStatus('Enter API Key and SKU'); return; }
                setLoading(true);
                setStatus('Analyzing... (this takes 1-2 minutes)');
                try {
                    const res = await fetch('/api/analyze', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({apiKey, eventSku: sku, myTeam})
                    });
                    const result = await res.json();
                    if (res.ok) {
                        setData(result);
                        setStatus('✅ Complete!');
                        setTab('picks');
                    } else {
                        setStatus('❌ ' + result.error);
                    }
                } catch(e) {
                    setStatus('❌ ' + e.message);
                }
                setLoading(false);
            };
            
            const exportCSV = () => {
                if (!data) return;
                const csv = [
                    ['Team','Rank','Auto','Quality','Avg Pts','SP','ML Prob','Synergy','Category'].join(','),
                    ...data.pickable.map(t => [
                        t.Team, t.Rank, t.Auto, t.Quality_Score, t.Avg_Pts, t.SP,
                        (t.ML_Win_Prob*100).toFixed(0)+'%', t.Synergy_Score, t.Traditional_Cat
                    ].join(','))
                ].join('\\n');
                const blob = new Blob([csv], {type: 'text/csv'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `vex_scout_${sku}.csv`;
                a.click();
            };
            
            return (
                <div className="container">
                    <div className="card">
                        <div className="title">🤖 VEX Scout v4</div>
                        <div>ML-Powered Alliance Selection</div>
                        {data && <div style={{fontSize:'14px',color:'#6b7280',marginTop:'5px'}}>📍 {data.eventName}</div>}
                    </div>
                    
                    <div className="card">
                        <div className="tabs">
                            <button className={'tab ' + (tab==='settings'?'active':'')} onClick={()=>setTab('settings')}>⚙️ Settings</button>
                            <button className={'tab ' + (tab==='picks'?'active':'')} onClick={()=>setTab('picks')} disabled={!data}>🎯 Picks</button>
                            <button className={'tab ' + (tab==='fraud'?'active':'')} onClick={()=>setTab('fraud')} disabled={!data}>⚠️ Frauds</button>
                            <button className={'tab ' + (tab==='stats'?'active':'')} onClick={()=>setTab('stats')} disabled={!data}>📊 Stats</button>
                        </div>
                        
                        {tab === 'settings' && (
                            <div>
                                <input type="password" placeholder="API Key" value={apiKey} onChange={e=>setApiKey(e.target.value)} />
                                <input placeholder="Event SKU (RE-V5RC-25-XXXX)" value={sku} onChange={e=>setSku(e.target.value)} />
                                <input placeholder="Your Team (8568A)" value={myTeam} onChange={e=>setMyTeam(e.target.value)} />
                                <button className="btn" onClick={analyze} disabled={loading} style={{width:'100%'}}>
                                    {loading ? '⏳ Analyzing...' : '🚀 Analyze Event'}
                                </button>
                                {data && <button className="btn" onClick={exportCSV} style={{width:'100%',background:'#10b981'}}>💾 Export CSV</button>}
                                <div className={'status ' + (status.includes('✅')?'status-success':status.includes('❌')?'status-error':'')}>{status}</div>
                            </div>
                        )}
                        
                        {tab === 'picks' && data && (
                            <div>
                                <h2>🎯 Best Picks for {myTeam} (Rank {data.myRank})</h2>
                                <p style={{fontSize:'14px',color:'#6b7280',marginBottom:'10px'}}>Teams you can select (ranked below you)</p>
                                {data.pickable.length > 0 ? (
                                    <div style={{overflowX:'auto'}}>
                                        <table>
                                            <thead>
                                                <tr>
                                                    <th>Team</th><th>Rank</th><th>Auto</th><th>Quality</th>
                                                    <th>Avg Pts</th><th>SP</th><th>ML Prob</th>
                                                    <th>Synergy</th><th>Category</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {data.pickable.map((t,i) => (
                                                    <tr key={i}>
                                                        <td><b>{t.Team}</b></td>
                                                        <td>{t.Rank}</td>
                                                        <td>{t.Auto}</td>
                                                        <td><span className="badge badge-purple">{t.Quality_Score}</span></td>
                                                        <td>{t.Avg_Pts}</td>
                                                        <td>{t.SP}</td>
                                                        <td>
                                                            <span className={`badge ${t.ML_Win_Prob>=0.7?'badge-green':t.ML_Win_Prob>=0.5?'badge-blue':'badge-yellow'}`}>
                                                                {(t.ML_Win_Prob*100).toFixed(0)}%
                                                            </span>
                                                        </td>
                                                        <td><span className={t.Synergy_Score>30?'badge badge-green':''}>{t.Synergy_Score>0?'+':''}{t.Synergy_Score}</span></td>
                                                        <td>{t.Traditional_Cat}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                ) : (
                                    <p style={{textAlign:'center',padding:'40px',color:'#6b7280'}}>No teams ranked below you</p>
                                )}
                                {data.recommended && (
                                    <div style={{marginTop:'20px',padding:'15px',background:'#d1fae5',borderRadius:'8px'}}>
                                        <div style={{fontWeight:'bold'}}>⭐ RECOMMENDED PICK: {data.recommended.Team}</div>
                                        <div style={{fontSize:'14px',color:'#065f46'}}>
                                            Rank {data.recommended.Rank} | ML: {(data.recommended.ML_Win_Prob*100).toFixed(0)}% | Synergy: +{data.recommended.Synergy_Score}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                        
                        {tab === 'fraud' && data && (
                            <div>
                                <h2 style={{color:'#dc2626'}}>⚠️ Fraud Watch</h2>
                                <p style={{fontSize:'14px',color:'#6b7280',marginBottom:'10px'}}>Top 8 rank but low ML probability</p>
                                {data.frauds.length > 0 ? (
                                    <div style={{overflowX:'auto'}}>
                                        <table>
                                            <thead style={{background:'#fee2e2'}}>
                                                <tr><th>Team</th><th>Rank</th><th>ML Prob</th><th>SP</th><th>Quality</th><th>Past Wins</th></tr>
                                            </thead>
                                            <tbody>
                                                {data.frauds.map((t,i) => (
                                                    <tr key={i}>
                                                        <td><b>{t.Team}</b></td>
                                                        <td>{t.Rank}</td>
                                                        <td><span className="badge badge-red">{(t.ML_Win_Prob*100).toFixed(0)}%</span></td>
                                                        <td style={{color:'#dc2626'}}>{t.SP}</td>
                                                        <td style={{color:'#dc2626'}}>{t.Quality_Score}</td>
                                                        <td>{t.Past_Wins}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                ) : (
                                    <div style={{textAlign:'center',padding:'40px'}}>
                                        <div style={{fontSize:'48px'}}>✅</div>
                                        <div style={{fontSize:'18px',fontWeight:500,color:'#059669'}}>No frauds!</div>
                                    </div>
                                )}
                            </div>
                        )}
                        
                        {tab === 'stats' && data && (
                            <div>
                                <h2>📊 Event Statistics</h2>
                                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:'15px',marginTop:'20px'}}>
                                    <div style={{padding:'15px',background:'#dbeafe',borderRadius:'8px'}}>
                                        <div style={{fontSize:'12px',color:'#6b7280'}}>Total Teams</div>
                                        <div style={{fontSize:'24px',fontWeight:'bold'}}>{data.totalTeams}</div>
                                    </div>
                                    <div style={{padding:'15px',background:'#d1fae5',borderRadius:'8px'}}>
                                        <div style={{fontSize:'12px',color:'#6b7280'}}>ML Top Picks</div>
                                        <div style={{fontSize:'24px',fontWeight:'bold'}}>{data.topPicks}</div>
                                    </div>
                                    <div style={{padding:'15px',background:'#fee2e2',borderRadius:'8px'}}>
                                        <div style={{fontSize:'12px',color:'#6b7280'}}>Fraud Watch</div>
                                        <div style={{fontSize:'24px',fontWeight:'bold'}}>{data.frauds.length}</div>
                                    </div>
                                    <div style={{padding:'15px',background:'#e9d5ff',borderRadius:'8px'}}>
                                        <div style={{fontSize:'12px',color:'#6b7280'}}>Sleepers</div>
                                        <div style={{fontSize:'24px',fontWeight:'bold'}}>{data.sleepers}</div>
                                    </div>
                                </div>
                                {data.myTeamData && (
                                    <div style={{marginTop:'20px',padding:'15px',background:'linear-gradient(to right, #dbeafe, #e9d5ff)',borderRadius:'8px'}}>
                                        <h3>📍 Your Team: {myTeam}</h3>
                                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'15px',marginTop:'10px'}}>
                                            <div><div style={{fontSize:'12px',color:'#6b7280'}}>Rank</div><div style={{fontSize:'20px',fontWeight:'bold'}}>{data.myTeamData.Rank}</div></div>
                                            <div><div style={{fontSize:'12px',color:'#6b7280'}}>Auto</div><div style={{fontSize:'20px',fontWeight:'bold'}}>{data.myTeamData.Auto}</div></div>
                                            <div><div style={{fontSize:'12px',color:'#6b7280'}}>Quality</div><div style={{fontSize:'20px',fontWeight:'bold'}}>{data.myTeamData.Quality_Score}</div></div>
                                            <div><div style={{fontSize:'12px',color:'#6b7280'}}>ML Prob</div><div style={{fontSize:'20px',fontWeight:'bold'}}>{(data.myTeamData.ML_Win_Prob*100).toFixed(0)}%</div></div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            );
        };
        
        ReactDOM.createRoot(document.getElementById('root')).render(<App />);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return Response(HTML_TEMPLATE, mimetype='text/html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        api_key = data.get('apiKey')
        event_sku = data.get('eventSku')
        my_team = data.get('myTeam', '')
        
        # Import your exact working functions
        import importlib.util
        spec = importlib.util.spec_from_file_location("vex_script", "iamjiangingit_v4_FINAL.py")
        vex_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vex_module)
        
        # Use your functions
        import joblib
        model_data = joblib.load('alliance_predictor.pkl')
        season_id = vex_module.get_push_back_id(api_key)
        
        # Run YOUR exact analysis function
        df, my_stats = vex_module.analyze_event_v5(
            event_sku, api_key, season_id, model_data,
            my_team if my_team else None
        )   
        
        # Prepare response
        my_rank = my_stats['Rank'] if my_stats else 999
        pickable = df[df['Rank'] > my_rank].sort_values('Partner_Score', ascending=False) if my_stats else df
        frauds = df[(df['ML_Win_Prob'] < 0.40) & (df['Rank'] <= 8)]
        
        # Count sleepers using the correct column name
        sleeper_count = len(df[df['Traditional_Cat'].str.contains('SLEEPER', na=False)])
        
        result = {
            "eventName": f"Event {event_sku}",
            "myRank": my_rank,
            "myTeamData": my_stats,
            "pickable": pickable.head(20).to_dict('records'),
            "frauds": frauds.to_dict('records'),
            "totalTeams": len(df),
            "topPicks": len(df[df['ML_Win_Prob'] >= 0.70]),
            "sleepers": sleeper_count,
            "recommended": pickable.iloc[0].to_dict() if len(pickable) > 0 else None
        }
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        print("ERROR:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n🚀 VEX Scout v4 Web Server")
    print("Server: http://localhost:5000\n")
    app.run(debug=True, port=5000)