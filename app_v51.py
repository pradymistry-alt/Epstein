from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import sys
import os

app = Flask(__name__)
CORS(app)

# Add the current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@app.route('/')
def index():
   # Remove 'templates/' from the path
return Response(open('index.html').read(), mimetype='text/html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        api_key = data.get('apiKey')
        event_sku = data.get('eventSku')
        my_team = data.get('myTeam', '')
        
        # Import the v5 analysis module
        import importlib.util
        spec = importlib.util.spec_from_file_location("vex_v5", "iamjiangingit_v5.py")
        vex_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vex_module)
        
        # Load ML model
        import joblib
        model_data = joblib.load('alliance_predictor.pkl')
        
        # Get season ID
        season_id = vex_module.get_push_back_id(api_key)
        
        # Run analysis
        df, my_stats, tiers, event_name = vex_module.analyze_event_v5(
            event_sku, api_key, season_id, model_data,
            my_team if my_team else None
        )
        
        if df is None or df.empty:
            return jsonify({'error': 'No data returned from analysis'}), 500
        
        # Prepare response data
        my_rank = my_stats['Rank'] if my_stats else 999
        
        # Get pickable teams (ranked below user)
        pickable = df[df['Rank'] > my_rank].sort_values('Partner_Score', ascending=False) if my_stats else df
        
        # Get frauds
        frauds = df[(df['ML_Win_Prob'] < 0.40) & (df['Rank'] <= 8)].to_dict('records')
        
        # Get special teams
        clutch_players = df[df['Clutch_Label'] == '🧊 CLUTCH'].sort_values('Clutch_Rate', ascending=False).head(10).to_dict('records')
        giant_killers = df[df['Upset_Label'] == '🔥 GIANT KILLER'].sort_values('Upset_Rate', ascending=False).head(10).to_dict('records')
        high_ceiling = df[df['Volatility_Type'] == 'HIGH_UPSIDE'].sort_values('Upside', ascending=False).head(10).to_dict('records')
        
        # Count sleepers
        sleeper_count = len(df[df['Traditional_Cat'].str.contains('SLEEPER', na=False)])
        
        # Build response
        result = {
            "eventName": event_name,
            "myRank": my_rank,
            "myTeamData": my_stats,
            "totalTeams": len(df),
            "topPicks": len(df[df['ML_Win_Prob'] >= 0.70]),
            "sleepers": sleeper_count,
            "frauds": frauds,
            "clutchPlayers": clutch_players,
            "giantKillers": giant_killers,
            "highCeiling": high_ceiling,
            "allPickable": pickable.head(30).to_dict('records'),
            "recommended": pickable.iloc[0].to_dict() if len(pickable) > 0 else None
        }
        
        # Add tier data if available
        if tiers:
            result["tierA"] = tiers['tier_a'].to_dict('records') if not tiers['tier_a'].empty else []
            result["tierB"] = tiers['tier_b'].to_dict('records') if not tiers['tier_b'].empty else []
            result["tierC"] = tiers['tier_c'].to_dict('records') if not tiers['tier_c'].empty else []
            result["tierSafe"] = tiers['tier_safe'].to_dict('records') if not tiers['tier_safe'].empty else []
            result["tierBoom"] = tiers['tier_boom'].to_dict('records') if not tiers['tier_boom'].empty else []
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        print("ERROR:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create templates directory if needed
    os.makedirs('templates', exist_ok=True)
    
    print("\n" + "="*60)
    print("🤖 VEX Scout v5 - Ultimate Edition")
    print("="*60)
    print("Server running at: http://localhost:5000")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000)
