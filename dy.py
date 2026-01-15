import requests
import json
import time

"""
DIAGNOSTIC SCRIPT
This will show us the actual structure of match data to fix elimination detection
"""

API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"

TEST_EVENT = "RE-V5RC-25-0179"  # Test with one event

def check_match_structure(sku, api_key):
    """Examine the actual structure of match data"""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    print(f"🔍 DIAGNOSTIC CHECK FOR: {sku}")
    print("="*80)
    
    # Get event
    time.sleep(0.5)
    r = requests.get(f"https://www.robotevents.com/api/v2/events?sku={sku}&include=divisions", headers=headers)
    event_data = r.json()['data'][0]
    event_id = event_data['id']
    divisions = event_data.get('divisions', [])
    
    print(f"✅ Event: {event_data['name']}")
    print(f"   Event ID: {event_id}")
    print(f"   Divisions: {len(divisions)}")
    
    # Get matches from first division
    if not divisions:
        print("❌ No divisions found!")
        return
    
    div_id = divisions[0]['id']
    print(f"\n📋 Fetching matches from division {div_id}...")
    
    time.sleep(0.5)
    r = requests.get(f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div_id}/matches?per_page=100", headers=headers)
    matches = r.json().get('data', [])
    
    if not matches:
        print("❌ No matches found!")
        return
    
    print(f"✅ Found {len(matches)} matches\n")
    
    # Analyze match types
    print("="*80)
    print("ANALYZING MATCH TYPES:")
    print("="*80)
    
    qual_matches = []
    elim_matches = []
    other_matches = []
    
    for match in matches:
        instance = match.get('instance')
        round_num = match.get('round')
        matchnum = match.get('matchnum')
        name = match.get('name', 'Unknown')
        
        if instance == 1:
            qual_matches.append(match)
        elif instance == 2:
            elim_matches.append(match)
        else:
            other_matches.append(match)
    
    print(f"Qualification matches (instance=1): {len(qual_matches)}")
    print(f"Elimination matches (instance=2): {len(elim_matches)}")
    print(f"Other/Unknown: {len(other_matches)}")
    
    # Show sample qualification match
    if qual_matches:
        print("\n" + "="*80)
        print("SAMPLE QUALIFICATION MATCH:")
        print("="*80)
        sample = qual_matches[0]
        print(json.dumps({
            'name': sample.get('name'),
            'round': sample.get('round'),
            'instance': sample.get('instance'),
            'matchnum': sample.get('matchnum'),
            'scheduled': sample.get('scheduled'),
            'started': sample.get('started'),
            'field': sample.get('field')
        }, indent=2))
    
    # Show sample elimination match (if any)
    if elim_matches:
        print("\n" + "="*80)
        print("SAMPLE ELIMINATION MATCH:")
        print("="*80)
        sample = elim_matches[0]
        print(json.dumps({
            'name': sample.get('name'),
            'round': sample.get('round'),
            'instance': sample.get('instance'),
            'matchnum': sample.get('matchnum'),
            'scheduled': sample.get('scheduled'),
            'started': sample.get('started'),
            'field': sample.get('field')
        }, indent=2))
        
        # Show teams in elimination match
        print("\nTeams in this elimination match:")
        alliances = sample.get('alliances', [])
        if isinstance(alliances, list):
            for alliance in alliances:
                color = alliance.get('color', 'unknown')
                teams = alliance.get('teams', [])
                print(f"  {color.upper()}: {len(teams)} teams")
                for t in teams:
                    if 'team' in t:
                        print(f"    - {t['team'].get('name', 'Unknown')} (ID: {t['team'].get('id')})")
    else:
        print("\n⚠️ NO ELIMINATION MATCHES FOUND!")
        print("This event either:")
        print("  1. Hasn't reached eliminations yet (still in qualifications)")
        print("  2. Is a scrimmage/qualifier without eliminations")
        print("  3. Hasn't uploaded elimination data to RobotEvents")
    
    # Check other matches
    if other_matches:
        print("\n" + "="*80)
        print("SAMPLE 'OTHER' MATCH (Unknown Type):")
        print("="*80)
        sample = other_matches[0]
        print(json.dumps({
            'name': sample.get('name'),
            'round': sample.get('round'),
            'instance': sample.get('instance'),
            'matchnum': sample.get('matchnum'),
            'scheduled': sample.get('scheduled'),
            'started': sample.get('started')
        }, indent=2))
    
    # Summary
    print("\n" + "="*80)
    print("DIAGNOSIS:")
    print("="*80)
    
    if len(elim_matches) == 0:
        print("❌ This event has NO elimination matches yet.")
        print("   Solution: Use events that are FULLY COMPLETED (have finals)")
        print("   Try looking for events from earlier in the season.")
    else:
        print(f"✅ This event has {len(elim_matches)} elimination matches")
        print("   The 'instance=2' check should work!")

if __name__ == "__main__":
    check_match_structure(TEST_EVENT, API_KEY)
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. If NO elim matches found → Use different events with completed elims")
    print("2. If elim matches found → The code should work, check for bugs")
    print("3. You can test other events by changing TEST_EVENT at the top")
    print("="*80)