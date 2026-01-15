<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VEX Scout v4 - Alliance Selection Tool</title>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .card { background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .card-header { padding: 20px; border-bottom: 1px solid #e5e7eb; }
        .card-body { padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }
        .title { font-size: 28px; font-weight: bold; color: #1f2937; }
        .subtitle { color: #6b7280; font-size: 14px; }
        .btn { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-weight: 500; display: inline-flex; align-items: center; gap: 8px; transition: all 0.2s; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover:not(:disabled) { background: #2563eb; }
        .btn-success { background: #10b981; color: white; }
        .btn-success:hover { background: #059669; }
        .btn-danger { background: #ef4444; color: white; }
        .tabs { display: flex; border-bottom: 2px solid #e5e7eb; overflow-x: auto; }
        .tab { padding: 12px 24px; border: none; background: none; cursor: pointer; font-weight: 500; color: #6b7280; border-bottom: 2px solid transparent; margin-bottom: -2px; white-space: nowrap; }
        .tab.active { color: #3b82f6; border-bottom-color: #3b82f6; }
        .tab:disabled { opacity: 0.5; cursor: not-allowed; }
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; font-weight: 500; margin-bottom: 5px; font-size: 14px; }
        .input-group input { width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; }
        .input-group input:focus { outline: none; border-color: #3b82f6; }
        .input-hint { font-size: 12px; color: #6b7280; margin-top: 4px; }
        .status { text-align: center; padding: 10px; border-radius: 6px; font-size: 14px; }
        .status-ready { background: #f3f4f6; color: #6b7280; }
        .status-success { background: #d1fae5; color: #065f46; }
        .status-error { background: #fee2e2; color: #991b1b; }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        thead { background: #f9fafb; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { font-weight: 600; color: #374151; }
        tr:hover { background: #f9fafb; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .badge-green { background: #d1fae5; color: #065f46; }
        .badge-blue { background: #dbeafe; color: #1e40af; }
        .badge-yellow { background: #fef3c7; color: #92400e; }
        .badge-red { background: #fee2e2; color: #991b1b; }
        .badge-purple { background: #e9d5ff; color: #6b21a8; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { padding: 15px; border-radius: 8px; }
        .stat-card.blue { background: #dbeafe; }
        .stat-card.green { background: #d1fae5; }
        .stat-card.red { background: #fee2e2; }
        .stat-card.purple { background: #e9d5ff; }
        .stat-label { font-size: 12px; color: #6b7280; margin-bottom: 5px; }
        .stat-value { font-size: 24px; font-weight: bold; }
        .alert { padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .alert-info { background: #dbeafe; border: 1px solid #93c5fd; }
        .alert-warning { background: #fef3c7; border: 1px solid #fcd34d; }
        .alert-success { background: #d1fae5; border: 1px solid #6ee7b7; }
        .empty-state { text-align: center; padding: 40px; color: #6b7280; }
        .empty-state-icon { font-size: 48px; margin-bottom: 10px; }
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 20px; overflow-y: auto; }
        .modal { background: white; border-radius: 12px; max-width: 900px; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 20px; border-bottom: 1px solid #e5e7eb; }
        .modal-body { padding: 20px; }
        .modal-close { background: none; border: none; font-size: 24px; cursor: pointer; color: #6b7280; }
        .modal-close:hover { color: #1f2937; }
        .legend-section { margin-bottom: 20px; }
        .legend-section h3 { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
        .legend-section.blue h3 { color: #2563eb; }
        .legend-section.green h3 { color: #059669; }
        .legend-section.purple h3 { color: #7c3aed; }
        .legend-section.red h3 { color: #dc2626; }
        .legend-section.orange h3 { color: #ea580c; }
        .legend-item { margin-bottom: 8px; font-size: 14px; }
        .legend-item strong { font-weight: 600; }
        .overflow-x-auto { overflow-x: auto; }
        @media (max-width: 768px) { .header { flex-direction: column; align-items: flex-start; } }
    </style>
</head>
<body>
    <div id="root"></div>
    
    <script type="text/babel">
        const { useState } = React;

        const VexScoutGUI = () => {
            const [activeTab, setActiveTab] = useState('settings');
            const [showLegend, setShowLegend] = useState(false);
            const [apiKey, setApiKey] = useState('');
            const [eventSku, setEventSku] = useState('');
            const [myTeam, setMyTeam] = useState('8568A');
            const [status, setStatus] = useState('Ready');
            const [loading, setLoading] = useState(false);
            const [teams, setTeams] = useState([]);
            const [eventName, setEventName] = useState('');
            const [stats, setStats] = useState({ total: 0, topPicks: 0, frauds: 0, sleepers: 0 });
            const [myTeamStats, setMyTeamStats] = useState(null);

            const analyzeEvent = async () => {
                if (!apiKey || !eventSku) {
                    setStatus('Please enter API Key and Event SKU');
                    return;
                }

                setLoading(true);
                setStatus('Analyzing event... This may take 1-2 minutes...');
                
                try {
                    const response = await fetch('http://localhost:5000/api/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            apiKey: apiKey,
                            eventSku: eventSku,
                            myTeam: myTeam
                        })
                    });
                    
                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.error || 'Analysis failed');
                    }
                    
                    const data = await response.json();
                    setTeams(data.teams);
                    setEventName(data.eventName);
                    setStats(data.stats);
                    setMyTeamStats(data.myTeam);
                    setStatus('✅ Analysis complete!');
                    setActiveTab('picks');
                } catch (error) {
                    setStatus('❌ Error: ' + error.message);
                }
                
                setLoading(false);
            };

            const exportToCSV = () => {
                if (teams.length === 0) {
                    alert('No data to export. Run analysis first.');
                    return;
                }

                const headers = ['Team', 'Rank', 'Auto', 'Quality Score', 'Avg Pts', 'SP', 'ML Prob', 'Category'];
                const csvData = teams.map(t => [
                    t.team, t.rank, t.auto, t.qualityScore, t.avgPts, t.sp,
                    (t.mlProb * 100).toFixed(0) + '%', t.category
                ].join(','));

                const csv = [headers.join(','), ...csvData].join('\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `vex_scout_${eventSku}.csv`;
                a.click();
            };

            const Legend = () => (
                <div className="modal-overlay" onClick={(e) => e.target.className === 'modal-overlay' && setShowLegend(false)}>
                    <div className="modal">
                        <div className="modal-header">
                            <h2>📚 Legend & Guide</h2>
                            <button className="modal-close" onClick={() => setShowLegend(false)}>✕</button>
                        </div>
                        <div className="modal-body">
                            <div className="legend-section blue">
                                <h3>📊 Metrics Explained</h3>
                                <div className="legend-item"><strong>Auto:</strong> Average autonomous points per match. 7.0+ is elite programming.</div>
                                <div className="legend-item"><strong>Avg Pts:</strong> Average total score per match. Shows offensive capability.</div>
                                <div className="legend-item"><strong>SP (Strength Points):</strong> Average opponent strength. High SP = beat tough teams.</div>
                                <div className="legend-item"><strong>ML Prob:</strong> Machine learning win probability (0-100%). Model's confidence.</div>
                                <div className="legend-item"><strong>Quality Score:</strong> Weighted metric: (Avg_Pts × 0.6) + (SP × 0.3) + (Win% × 10). Better than raw scoring!</div>
                            </div>

                            <div className="legend-section green">
                                <h3>🏆 Categories</h3>
                                <div className="legend-item"><strong>🏆 ELITE:</strong> Top 5 rank + high ML prob. Proven champions.</div>
                                <div className="legend-item"><strong>🚀 SLEEPER:</strong> Rank 10+ but high ML probability. BEST VALUE PICKS!</div>
                                <div className="legend-item"><strong>⚠️ FRAUD:</strong> Top 8 rank but low ML + weak schedule. First-round exit risk!</div>
                                <div className="legend-item"><strong>📊 SOLID:</strong> Reliable, consistent teams.</div>
                            </div>

                            <div className="legend-section purple">
                                <h3>🎯 Alliance Selection Strategy</h3>
                                <div className="legend-item"><strong>If you're Rank 1-8:</strong> You're an alliance captain. Pick SLEEPERS ranked 10-20 with high ML probability.</div>
                                <div className="legend-item"><strong>If you're Rank 9-16:</strong> Last captain or getting picked. Target high Quality Score teams.</div>
                                <div className="legend-item"><strong>If you're Rank 17+:</strong> Focus on synergy with potential captains.</div>
                                <div className="alert alert-warning" style={{marginTop: '10px'}}>
                                    <strong>Golden Rule:</strong> A rank 15 SLEEPER (ML: 68%) beats a rank 8 FRAUD (ML: 28%) every time!
                                </div>
                            </div>

                            <div className="legend-section orange">
                                <h3>🔬 Quality Score Explained</h3>
                                <div className="legend-item"><strong>Why it matters:</strong></div>
                                <div className="legend-item">• Team A: 45 avg pts, SP 12.3 (beat weak teams) → Quality: 52</div>
                                <div className="legend-item">• Team B: 38 avg pts, SP 19.8 (beat strong teams) → Quality: 68</div>
                                <div className="alert alert-info" style={{marginTop: '10px'}}>
                                    Team B is better! High-level matches are low-scoring defensive battles. Quality Score captures this.
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            );

            const myRank = myTeamStats ? myTeamStats.rank : 999;
            const pickableTeams = teams.filter(t => t.team !== myTeam && t.rank > myRank);
            const fraudTeams = teams.filter(t => t.category === '⚠️ FRAUD');
            const statusClass = status.includes('✅') ? 'status-success' : status.includes('❌') ? 'status-error' : 'status-ready';

            return (
                <div className="container">
                    <div className="card">
                        <div className="card-header">
                            <div className="header">
                                <div>
                                    <div className="title">🤖 iamjiangingit v4</div>
                                    <div className="subtitle">ML-Powered VEX Alliance Selection</div>
                                    {eventName && <div className="subtitle">📍 {eventName}</div>}
                                </div>
                                <div style={{display: 'flex', gap: '10px'}}>
                                    <button className="btn btn-primary" onClick={() => setShowLegend(true)}>
                                        ℹ️ Legend
                                    </button>
                                    <button className="btn btn-success" onClick={exportToCSV}>
                                        💾 Export CSV
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="card">
                        <div className="tabs">
                            <button className={`tab ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>⚙️ Settings</button>
                            <button className={`tab ${activeTab === 'picks' ? 'active' : ''}`} onClick={() => setActiveTab('picks')} disabled={teams.length === 0}>🎯 Your Picks</button>
                            <button className={`tab ${activeTab === 'fraud' ? 'active' : ''}`} onClick={() => setActiveTab('fraud')} disabled={teams.length === 0}>⚠️ Fraud Watch</button>
                            <button className={`tab ${activeTab === 'analysis' ? 'active' : ''}`} onClick={() => setActiveTab('analysis')} disabled={teams.length === 0}>📊 Analysis</button>
                        </div>

                        <div className="card-body">
                            {activeTab === 'settings' && (
                                <div>
                                    <div className="input-group">
                                        <label>API Key</label>
                                        <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Enter your RobotEvents API key" />
                                        <div className="input-hint">Get your API key from robotevents.com</div>
                                    </div>
                                    <div className="input-group">
                                        <label>Event SKU</label>
                                        <input type="text" value={eventSku} onChange={(e) => setEventSku(e.target.value)} placeholder="RE-V5RC-25-XXXX" />
                                        <div className="input-hint">Find this in the event URL on robotevents.com</div>
                                    </div>
                                    <div className="input-group">
                                        <label>Your Team Number</label>
                                        <input type="text" value={myTeam} onChange={(e) => setMyTeam(e.target.value)} placeholder="8568A" />
                                    </div>
                                    <button className="btn btn-primary" style={{width: '100%', justifyContent: 'center'}} onClick={analyzeEvent} disabled={loading}>
                                        {loading ? '⏳ Analyzing...' : '🚀 Analyze Event'}
                                    </button>
                                    <div className={`status ${statusClass}`} style={{marginTop: '15px'}}>{status}</div>
                                </div>
                            )}

                            {activeTab === 'picks' && (
                                <div>
                                    <h2 style={{marginBottom: '5px'}}>🎯 Best Picks for {myTeam}</h2>
                                    <p style={{color: '#6b7280', fontSize: '14px', marginBottom: '15px'}}>Teams YOU can select (ranked below you at rank {myRank})</p>
                                    {pickableTeams.length > 0 ? (
                                        <div className="overflow-x-auto">
                                            <table>
                                                <thead>
                                                    <tr>
                                                        <th>Team</th>
                                                        <th>Rank</th>
                                                        <th>Auto</th>
                                                        <th>Quality</th>
                                                        <th>Avg Pts</th>
                                                        <th>SP</th>
                                                        <th>ML Prob</th>
                                                        <th>Category</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {pickableTeams.slice(0, 15).map((team, idx) => (
                                                        <tr key={idx}>
                                                            <td><strong>{team.team}</strong></td>
                                                            <td>{team.rank}</td>
                                                            <td>{team.auto}</td>
                                                            <td><span className="badge badge-purple">{team.qualityScore}</span></td>
                                                            <td>{team.avgPts}</td>
                                                            <td>{team.sp}</td>
                                                            <td>
                                                                <span className={`badge ${team.mlProb >= 0.7 ? 'badge-green' : team.mlProb >= 0.5 ? 'badge-blue' : 'badge-yellow'}`}>
                                                                    {(team.mlProb * 100).toFixed(0)}%
                                                                </span>
                                                            </td>
                                                            <td>{team.category}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    ) : (
                                        <div className="empty-state">
                                            <div className="empty-state-icon">🤷</div>
                                            <div>No teams ranked below you. You'll likely be picked by a higher-ranked team.</div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {activeTab === 'fraud' && (
                                <div>
                                    <h2 style={{marginBottom: '5px', color: '#dc2626'}}>⚠️ Fraud Watch</h2>
                                    <p style={{color: '#6b7280', fontSize: '14px', marginBottom: '15px'}}>High rank but low ML probability - first-round exit risk!</p>
                                    {fraudTeams.length > 0 ? (
                                        <div className="overflow-x-auto">
                                            <table>
                                                <thead style={{background: '#fee2e2'}}>
                                                    <tr>
                                                        <th>Team</th>
                                                        <th>Rank</th>
                                                        <th>ML Prob</th>
                                                        <th>SP</th>
                                                        <th>Quality Score</th>
                                                        <th>Auto</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {fraudTeams.map((team, idx) => (
                                                        <tr key={idx}>
                                                            <td><strong>{team.team}</strong></td>
                                                            <td>{team.rank}</td>
                                                            <td><span className="badge badge-red">{(team.mlProb * 100).toFixed(0)}%</span></td>
                                                            <td style={{color: '#dc2626'}}>{team.sp} (weak)</td>
                                                            <td style={{color: '#dc2626'}}>{team.qualityScore}</td>
                                                            <td>{team.auto}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    ) : (
                                        <div className="empty-state">
                                            <div className="empty-state-icon">✅</div>
                                            <div style={{fontSize: '18px', fontWeight: 500, color: '#059669', marginBottom: '5px'}}>No frauds detected!</div>
                                            <div>Top 8 teams all look solid</div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {activeTab === 'analysis' && (
                                <div>
                                    <div className="stats-grid">
                                        <div className="stat-card blue">
                                            <div className="stat-label">Total Teams</div>
                                            <div className="stat-value">{stats.total}</div>
                                        </div>
                                        <div className="stat-card green">
                                            <div className="stat-label">ML Top Picks (70%+)</div>
                                            <div className="stat-value">{stats.topPicks}</div>
                                        </div>
                                        <div className="stat-card red">
                                            <div className="stat-label">Fraud Watch</div>
                                            <div className="stat-value">{stats.frauds}</div>
                                        </div>
                                        <div className="stat-card purple">
                                            <div className="stat-label">Sleepers</div>
                                            <div className="stat-value">{stats.sleepers}</div>
                                        </div>
                                    </div>

                                    {myTeamStats && (
                                        <div className="alert alert-info">
                                            <h3 style={{marginBottom: '10px'}}>📍 Your Team: {myTeam}</h3>
                                            <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '15px', fontSize: '14px'}}>
                                                <div>
                                                    <div className="stat-label">Rank</div>
                                                    <div style={{fontSize: '20px', fontWeight: 'bold'}}>{myTeamStats.rank}</div>
                                                </div>
                                                <div>
                                                    <div className="stat-label">Auto</div>
                                                    <div style={{fontSize: '20px', fontWeight: 'bold'}}>{myTeamStats.auto}</div>
                                                </div>
                                                <div>
                                                    <div className="stat-label">Quality Score</div>
                                                    <div style={{fontSize: '20px', fontWeight: 'bold'}}>{myTeamStats.qualityScore}</div>
                                                </div>
                                                <div>
                                                    <div className="stat-label">ML Prob</div>
                                                    <div style={{fontSize: '20px', fontWeight: 'bold'}}>{(myTeamStats.mlProb * 100).toFixed(0)}%</div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    <div style={{marginTop: '20px'}}>
                                        <div className="alert alert-success">
                                            <h3 style={{marginBottom: '5px'}}>🚀 Sleepers (Best Value)</h3>
                                            <div style={{fontSize: '14px'}}>{stats.sleepers} teams found - Rank 10+ with high ML probability</div>
                                        </div>
                                        <div className="alert alert-warning">
                                            <h3 style={{marginBottom: '5px'}}>⚠️ Fraud Watch</h3>
                                            <div style={{fontSize: '14px'}}>{stats.frauds} teams at risk - Top 8 rank but low ML score</div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {showLegend && <Legend />}
                </div>
            );
        };

        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<VexScoutGUI />);
    </script>
</body>
</html>