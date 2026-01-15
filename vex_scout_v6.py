"""
================================================================================
 VEX SCOUT v11 - EYE TEST EDITION
 Fully Commented for VEX Think Award Submission
================================================================================

 WHAT THIS PROGRAM DOES:
 -----------------------
 This is a Machine Learning-powered alliance selection assistant for VEX Robotics
 competitions. It analyzes team performance data from RobotEvents API and helps
 scouts identify the best alliance partners, detect overrated teams ("frauds"),
 and find underrated "sleeper" picks that could win tournaments.

 NEW FEATURES IN v11 (Based on Real Competition Feedback):
 ---------------------------------------------------------
 1. MANUAL OVERRIDE: Users can rate teams 1-10 based on what they SEE at the
    competition. This rating overrides the AI score because human observation
    catches things data can't (driver skill, robot reliability, team communication)
 
 2. HEAD-TO-HEAD TRACKER: Input who beat who in elimination matches. This is
    crucial because a team that lost to you in elims shouldn't be ranked above you!
 
 3. "CHOKES IN ELIMS" FLAG: Tracks which round teams exit in playoffs. A team
    ranked #2 that loses in quarterfinals is a "fraud" - they can't perform
    when it matters.
 
 4. CURRENT SEASON ONLY: Old awards (like Worlds 2nd place from 3 years ago)
    are ignored. Teams graduate, players quit - past success doesn't guarantee
    current performance.
 
 5. ELIM WIN RATE: Separate from qualification win rate. A team that goes 8-2
    in quals but 0-2 in elims is NOT a good alliance partner.

 HOW THE ALGORITHM WORKS:
 ------------------------
 The program uses multiple data sources to create a comprehensive team rating:
 
 1. TrueSkill Rating System: A Bayesian skill rating (like chess ELO but better)
    that accounts for team-based competition. Each win/loss updates a team's
    estimated skill level with uncertainty bounds.
 
 2. OPR (Offensive Power Rating): Uses linear algebra to separate each team's
    individual contribution from alliance scores. If Alliance A scores 50 points
    and Alliance B scores 40, OPR figures out how much each of the 4 robots
    contributed.
 
 3. Machine Learning Model: A Random Forest classifier trained on past tournament
    data to predict which teams will be successful (reach finals, win awards).
 
 4. Contextual Factors: Skills scores (proves robot works solo), autonomous
    performance, consistency (standard deviation), clutch performance in close
    games, and trend analysis (improving vs declining).

 AUTHOR: Built with Claude AI assistance
 PURPOSE: VEX V5 Robotics Competition alliance selection
 SEASON: 2025-2026 Push Back
================================================================================
"""

# =============================================================================
# IMPORTS - External libraries needed to run this program
# =============================================================================

import os                    # File system operations (checking if files exist)
import joblib                # Save/load machine learning models
import pandas as pd          # Data manipulation and analysis
import numpy as np           # Numerical computing (arrays, math operations)
import math                  # Mathematical functions (erf for TrueSkill)
import requests              # HTTP requests to RobotEvents API
import traceback             # Error tracking and debugging
import time                  # Delays and timestamps
import json                  # JSON file reading/writing for data persistence
from flask import Flask, request, jsonify, Response  # Web server framework
from flask_cors import CORS  # Allow cross-origin requests (needed for frontend)
from sklearn.ensemble import RandomForestClassifier  # Machine learning model

# =============================================================================
# TRUESKILL RATING SYSTEM
# =============================================================================
# TrueSkill is a Bayesian skill rating system developed by Microsoft for Xbox
# Live matchmaking. Unlike simple win/loss records, it:
# - Accounts for uncertainty (new teams have high uncertainty)
# - Handles team-based games (separates individual skill from team performance)
# - Converges quickly to true skill level
#
# Each team has two values:
# - mu (μ): Estimated skill level (starts at 25)
# - sigma (σ): Uncertainty in that estimate (starts at 8.333)
#
# Conservative estimate = mu - 3*sigma (99.7% confident they're at least this good)
# =============================================================================

class TrueSkillRating:
    """
    Represents a team's TrueSkill rating.
    
    Attributes:
        mu (float): The estimated skill level (average performance)
        sigma (float): The uncertainty/variance in the skill estimate
    
    The 'conservative' property returns mu - 3*sigma, which is a lower bound
    on the team's skill that we're 99.7% confident about.
    """
    def __init__(self, mu=25.0, sigma=8.333):
        self.mu = mu          # Starting skill estimate
        self.sigma = sigma    # Starting uncertainty (high = we don't know much)
    
    @property
    def conservative(self):
        """
        Returns a conservative skill estimate.
        This is the skill level we're 99.7% confident the team is AT LEAST at.
        Used for ranking to avoid overrating teams we haven't seen much of.
        """
        return self.mu - 3 * self.sigma


def update_trueskill(winner_ratings, loser_ratings, margin=0):
    """
    Updates TrueSkill ratings after a match.
    
    This implements the core TrueSkill update equations. When a team wins,
    their mu increases and sigma decreases (we're more certain about their skill).
    When they lose, the opposite happens.
    
    The math uses Gaussian distributions and is based on the paper:
    "TrueSkill: A Bayesian Skill Rating System" by Herbrich et al.
    
    Parameters:
        winner_ratings (list): TrueSkillRating objects for winning alliance
        loser_ratings (list): TrueSkillRating objects for losing alliance
        margin (int): Point differential (bigger wins = bigger rating changes)
    """
    # Beta squared represents the variance of game outcomes
    # Higher beta = more randomness in the game
    beta = 4.1667
    
    # Calculate average skill and combined uncertainty for each alliance
    winner_mu = sum(r.mu for r in winner_ratings) / len(winner_ratings)
    winner_sigma = sum(r.sigma**2 for r in winner_ratings)**0.5 / len(winner_ratings)
    loser_mu = sum(r.mu for r in loser_ratings) / len(loser_ratings)
    loser_sigma = sum(r.sigma**2 for r in loser_ratings)**0.5 / len(loser_ratings)
    
    # c is the total uncertainty in the match outcome
    c = (2 * beta**2 + winner_sigma**2 + loser_sigma**2)**0.5
    
    # t is the normalized skill difference
    t = (winner_mu - loser_mu) / c
    
    # v and w are update multipliers from the TrueSkill equations
    # They use the Gaussian probability density function
    # math.erf is the error function used in normal distribution calculations
    v = math.exp(-t**2 / 2) / (0.5 * (1 + math.erf(t / 2**0.5)) * (2 * math.pi)**0.5 + 0.001)
    w = v * (v + t)
    
    # Bigger wins (higher margin) cause bigger rating changes
    margin_factor = 1 + min(margin / 50, 0.5)
    
    # Update winner ratings (skill goes UP, uncertainty goes DOWN)
    for r in winner_ratings:
        r.mu += (r.sigma**2 / c) * v * margin_factor
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)
    
    # Update loser ratings (skill goes DOWN, uncertainty goes DOWN slightly)
    for r in loser_ratings:
        r.mu -= (r.sigma**2 / c) * v * margin_factor
        r.sigma = max(1.0, r.sigma * (1 - (r.sigma**2 / c**2) * w * 0.5)**0.5)


# =============================================================================
# CONFIGURATION AND GLOBAL VARIABLES
# =============================================================================

# RobotEvents API key - allows access to competition data
# This is a public API key for educational/scouting purposes
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzIiwianRpIjoiYTNmZTVmNjVhZTY4OGU4ODBlOWE0ZWJlMDQ5YTE5MGI1M2NkZDY3NjRjY2IwNTAyYmFjNDRkMTQ3MjMxMTA5ZWQxMTU0OWMzZjAxNDI4MjYiLCJpYXQiOjE3NjU5MTkyNjMuOTM1OTUxLCJuYmYiOjE3NjU5MTkyNjMuOTM1OTUyOSwiZXhwIjoyNzEyNjA0MDYzLjkyOTg4NCwic3ViIjoiMTU1OTg4Iiwic2NvcGVzIjpbXX0.cG2Vk0WcgmeDHvbmnFda4YAQYS5gag02lrZIWyT9vg27b0nyUyjVn7BHbDc-bbz4nsVxhZfFEPuLWZYWHvuOx-hOXyRead_BehoEFIcfj-ufTMrJuFjTxrQZNdwCqYA7d5pZW_HCDNT0h6wawzeLWKBnDIHRL1PchIllKW6qRKd8OXZW4dI4ts-srRX5lIOPl4W3Nyn6BzGOuhtVgwGJXWchO3nztiqvpzT1sS9XoWNNFiHpke_KljJ6m4EnKu96XusTjLEaWyhf7w1fuMOIp37MzXCvUF5HpRQiX5NMzPJqCAf5YOmrDBb7sNio-ycofVYeVvdnoRRxfp80Ujdv5s8COiicR9TcpJPl2uFQy5DY-gKFshUenUeAmYjLiKPNrAF_dRMDnfDtY8gCiZ_qOxpxcv-1qlqT5vntkOU2ieJsSsu0-Io3ETpnQI9lsPum8fXTAS98P7uPtJG63r1GEZlNAStEmcovG0pIZ7MSAN7R5y5XPoOeWXN-6PZq6BzCtNTyVziXxUfrWcgUQVSZV398XV_BRNA_TzWITn-pq55uum0oQ2bOG609enCSLJBZnSUHPV9fGpTBBWOHq94uNvLisvVEJwvfZcyc605K5YvTxeFUdBBGtRh4uv5ZOuSbrB-hKJmNwDglnzeQL-76hIKFqpgXpBmE7Xsf_Bxwmq0"

# File names for persistent storage
MODEL_FILE = 'scout_brain_v11.pkl'      # Trained ML model
NOTES_FILE = 'team_notes.json'          # User's notes on teams
CACHE_FILE = 'event_cache.json'         # Cached analysis data
RATINGS_FILE = 'manual_ratings.json'    # NEW v11: User's manual 1-10 ratings
H2H_FILE = 'head_to_head.json'          # NEW v11: Head-to-head results

# Initialize Flask web application
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for frontend

# Global state variables
live_state = {
    'picked': [],      # Teams already picked in alliance selection
    'alliances': {},   # Formed alliances
    'bracket': []      # Elimination bracket data
}

team_notes = {}        # {team_name: "note text"} - scouting notes
manual_ratings = {}    # NEW v11: {team_name: 1-10} - user's eye test ratings
head_to_head = []      # NEW v11: [{winner, loser, round}] - elim match results
progress = {'status': 'idle', 'step': '', 'percent': 0, 'detail': ''}  # Loading progress
cached_data = {}       # Stores last analysis for quick refresh
event_cache = {}       # Cached event metadata


# =============================================================================
# DATA PERSISTENCE - Load saved data from files
# =============================================================================
# This section loads any previously saved data when the program starts.
# This allows users to close the program and resume later without losing:
# - Their scouting notes
# - Their manual ratings
# - Head-to-head results they've entered
# =============================================================================

for filename, target in [
    (NOTES_FILE, 'notes'),
    (CACHE_FILE, 'cache'),
    (RATINGS_FILE, 'ratings'),
    (H2H_FILE, 'h2h')
]:
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as file:
                data = json.load(file)
                if target == 'notes':
                    team_notes = data
                elif target == 'cache':
                    event_cache = data
                elif target == 'ratings':
                    manual_ratings = data
                elif target == 'h2h':
                    head_to_head = data
        except Exception as e:
            # If file is corrupted, just start fresh
            print(f"Warning: Could not load {filename}: {e}")
            pass


def save_file(filename, data):
    """
    Saves data to a JSON file for persistence.
    
    Parameters:
        filename (str): Name of file to save to
        data (dict/list): Data to save (must be JSON-serializable)
    """
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)  # indent=2 makes file human-readable


# =============================================================================
# API REQUEST HELPER
# =============================================================================

def safe_request(url, headers, delay=0.15, retries=3):
    """
    Makes an HTTP GET request with error handling and rate limiting.
    
    The RobotEvents API has rate limits, so we:
    1. Add a small delay between requests (0.15 seconds)
    2. Retry failed requests up to 3 times
    3. Handle 429 (Too Many Requests) errors with exponential backoff
    
    Parameters:
        url (str): The API endpoint URL
        headers (dict): HTTP headers (includes API key)
        delay (float): Seconds to wait before request
        retries (int): Number of retry attempts
    
    Returns:
        dict: JSON response data, or None if request failed
    """
    time.sleep(delay)  # Rate limiting - don't hammer the API
    
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            
            # Handle rate limiting (API says "slow down")
            if r.status_code == 429:
                wait_time = (attempt + 1) * 3  # 3, 6, 9 seconds
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            # Server error - probably temporary
            if r.status_code >= 500:
                return None
            
            return r.json()
            
        except Exception as e:
            if attempt == retries - 1:
                print(f"Request failed after {retries} attempts: {e}")
                return None
            time.sleep(1)
    
    return None


# =============================================================================
# GRADING SYSTEM
# =============================================================================

def get_grade(score, all_scores):
    """
    Converts a numerical score to a letter grade using percentile-based curves.
    
    This uses a curved grading system based on where a team ranks compared to
    all other teams at the event. Top 5% get A+, bottom 6% get F, etc.
    
    Parameters:
        score (float): The team's overall score
        all_scores (list): All teams' scores at the event
    
    Returns:
        str: Letter grade (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, F)
    """
    if not all_scores or len(all_scores) < 5:
        return 'C'  # Not enough data to grade fairly
    
    # Calculate what percentile this score is at
    percentile = sum(1 for s in all_scores if score > s) / len(all_scores)
    
    # Assign grade based on percentile
    if percentile >= 0.95: return 'A+'   # Top 5%
    if percentile >= 0.88: return 'A'    # Top 12%
    if percentile >= 0.80: return 'A-'   # Top 20%
    if percentile >= 0.70: return 'B+'   # Top 30%
    if percentile >= 0.60: return 'B'    # Top 40%
    if percentile >= 0.50: return 'B-'   # Top 50%
    if percentile >= 0.40: return 'C+'   # Top 60%
    if percentile >= 0.30: return 'C'    # Top 70%
    if percentile >= 0.20: return 'C-'   # Top 80%
    if percentile >= 0.12: return 'D+'   # Top 88%
    if percentile >= 0.06: return 'D'    # Top 94%
    return 'F'                           # Bottom 6%


# =============================================================================
# MATCH TYPE DETECTION
# =============================================================================

def is_elim_match(name):
    """
    Determines if a match is an elimination (playoff) match and which round.
    
    This is important because elimination matches are MORE valuable than
    qualification matches - they show how teams perform under pressure.
    
    Parameters:
        name (str): Match name from API (e.g., "Q-15", "SF1-1", "F-2")
    
    Returns:
        tuple: (is_elim: bool, round_name: str, round_weight: int)
               round_weight is used to track how far teams advance
               (higher = further in bracket)
    """
    if not name:
        return False, None, 0
    
    n = name.upper()
    
    # Check for different elimination round formats
    if 'F-' in n or 'FINAL' in n:
        return True, 'Finals', 4
    if 'SF' in n or 'SEMI' in n:
        return True, 'Semifinals', 3
    if 'QF' in n or 'QUARTER' in n:
        return True, 'Quarterfinals', 2
    if 'R16' in n:
        return True, 'Round of 16', 1
    
    return False, None, 0


def get_elim_exit_round(matches):
    """
    Determines what round a team exited the elimination bracket.
    
    NEW IN v11: This is crucial for detecting "chokes in elims" - teams that
    are ranked high but consistently lose early in playoffs.
    
    Parameters:
        matches (list): List of match dictionaries for a team
    
    Returns:
        tuple: (exit_round_name: str, exit_round_number: int)
    """
    elim_matches = [m for m in matches if m.get('is_elim')]
    
    if not elim_matches:
        return None, 0  # Team didn't play in elims
    
    # Map round names to numbers
    round_weights = {
        'Round of 16': 1,
        'Quarterfinals': 2,
        'Semifinals': 3,
        'Finals': 4
    }
    
    # Find the furthest round they reached
    max_round = 0
    max_round_name = None
    
    for match in elim_matches:
        round_name = match.get('elim_round')
        weight = round_weights.get(round_name, 0)
        if weight > max_round:
            max_round = weight
            max_round_name = round_name
    
    # Special case: Check if they WON the finals (they're champions!)
    finals_matches = [m for m in elim_matches if m.get('elim_round') == 'Finals']
    if finals_matches and all(m.get('won') for m in finals_matches):
        return 'Champion', 5
    
    return max_round_name, max_round


# =============================================================================
# SLEEPER DETECTION
# =============================================================================
# A "sleeper" is a team that's underrated - they have a low event rank but
# could potentially cause upsets. These are the hidden gems that smart
# alliance captains look for.
#
# Real example: At a recent competition, the #17 seed team won the tournament!
# A good sleeper detection algorithm would have identified them.
# =============================================================================

def calculate_sleeper_score(team_data):
    """
    Calculates how likely a team is to be an underrated "sleeper" pick.
    
    Sleepers are teams with:
    - High ceiling (their best matches are really good)
    - Strong skills score (proves robot works without random partners)
    - Improving trend (getting better throughout the event)
    - Wins against higher-ranked teams (can compete with the best)
    - Good auto (reliable points every match)
    - Clutch performance (wins close games)
    
    Parameters:
        team_data (dict): Team statistics
    
    Returns:
        tuple: (sleeper_score: int, reasons: list of strings)
    """
    score = 0
    reasons = []
    
    rank = team_data.get('Rank', 50)
    
    # Can't be a sleeper if you're already ranked in top 10
    # (by definition, sleepers are underrated)
    if rank <= 10:
        return 0, []
    
    # HIGH CEILING: Team's best performances are significantly above average
    # This means they CAN pop off and score big when it matters
    ceiling = team_data.get('Ceiling', 0)
    avg = team_data.get('Avg_Pts', 0)
    if ceiling > avg * 1.25:  # Ceiling 25%+ above average
        score += 20
        reasons.append(f"🚀 High ceiling ({ceiling:.0f} vs {avg:.0f} avg)")
    
    # STRONG SKILLS: Skills matches are SOLO - no random partner
    # High skills proves the ROBOT is good, not just lucky partners
    skills = team_data.get('Skills', 0)
    if skills >= 80:
        score += 25
        reasons.append(f"🎮 Strong skills ({skills})")
    elif skills >= 50:
        score += 12
        reasons.append(f"🎮 Decent skills ({skills})")
    
    # STRONG AUTO: Autonomous points are guaranteed every match
    # Good auto = reliable foundation regardless of alliance partner
    auto = team_data.get('Auto', 0)
    if auto >= 7:
        score += 20
        reasons.append(f"🤖 Elite auto ({auto})")
    elif auto >= 5.5:
        score += 10
        reasons.append(f"🤖 Good auto ({auto})")
    
    # IMPROVING TREND: Second half scores > first half scores
    # Teams that are improving will peak in eliminations
    trend = team_data.get('Trend', 0)
    if trend >= 8:
        score += 18
        reasons.append(f"📈 Hot streak (+{trend:.0f})")
    elif trend >= 4:
        score += 8
        reasons.append("📈 Improving")
    
    # GIANT KILLER: Wins against higher-ranked teams
    # Proves they can compete at a high level
    wins_vs_higher = team_data.get('Wins_vs_Higher', 0)
    if wins_vs_higher >= 3:
        score += 20
        reasons.append(f"⚔️ Giant killer ({wins_vs_higher} upsets)")
    elif wins_vs_higher >= 2:
        score += 10
        reasons.append(f"⚔️ Beat {wins_vs_higher} higher ranked")
    
    # UNDERRANKED BY TRUESKILL: Low event rank but high actual skill
    # This often happens when good teams have bad luck with partners
    ts = team_data.get('TrueSkill_Mu', 25)
    if rank > 15 and ts >= 27:
        score += 15
        reasons.append(f"🎯 Underranked (TS:{ts:.0f})")
    
    # CLUTCH PERFORMER: Wins close games
    clutch = team_data.get('Clutch_Rate', 0.5)
    close_matches = team_data.get('Close_Matches', 0)
    if close_matches >= 3 and clutch >= 0.6:
        score += 12
        reasons.append(f"🧊 Clutch ({int(clutch*100)}%)")
    
    # ELIM PERFORMANCE: NEW v11 - wins in elims are HUGE
    elim_wins = team_data.get('Elim_Wins', 0)
    if elim_wins >= 3:
        score += 25
        reasons.append(f"🏆 {elim_wins} elim wins!")
    elif elim_wins >= 1:
        score += 12
        reasons.append("🏆 Won in elims")
    
    # BLOWOUT WINS: Shows they can dominate, not just squeak by
    blowouts = team_data.get('Blowout_Wins', 0)
    if blowouts >= 2:
        score += 10
        reasons.append(f"💪 {blowouts} blowout wins")
    
    # HIDDEN VALUE: Being ranked very low increases the "steal" value
    if rank >= 20:
        score += 8
        reasons.append(f"💎 Hidden at #{rank}")
    
    return score, reasons


# =============================================================================
# FRAUD DETECTION
# =============================================================================
# A "fraud" is a team that's OVERRATED - they have a high rank but will
# likely choke in eliminations. Picking a fraud as your alliance partner
# is a recipe for early elimination.
#
# Real example: At a competition, the #1 seed lost with the #7 seed while
# the #17 seed won with the #2 seed. The algorithm should detect these!
# =============================================================================

def detect_fraud(team_data, global_avg_sp, h2h_losses):
    """
    Detects overrated teams that will likely choke in eliminations.
    
    NEW IN v11: Now includes head-to-head data! If a team LOST to another
    team in elims, that's a huge red flag.
    
    Fraud indicators:
    - Lost to lower-ranked teams (can't beat who they should)
    - Chokes close games (bad under pressure)
    - Early elim exits (can't perform when it matters)
    - Weak schedule (beat bad teams to get high rank)
    - Low skills (robot isn't actually that good)
    - Declining trend (getting worse as event goes on)
    - Lost head-to-head in elims
    
    Parameters:
        team_data (dict): Team statistics
        global_avg_sp (float): Average strength of schedule at event
        h2h_losses (list): Head-to-head losses from user input
    
    Returns:
        tuple: (is_fraud: bool, red_flags: list of strings, fraud_score: int)
    """
    score = 0
    flags = []
    
    rank = team_data.get('Rank', 99)
    
    # Only check high-ranked teams for fraud
    # Low-ranked teams can't be "overrated"
    if rank > 12:
        return False, [], 0
    
    # LOST TO LOWER RANKED: This should NOT happen for a top team
    losses_to_lower = team_data.get('Losses_to_Lower_This_Event', 0)
    if losses_to_lower >= 2:
        score += 25
        flags.append(f"Lost {losses_to_lower}x to lower ranked")
    elif losses_to_lower >= 1 and rank <= 5:
        score += 12
        flags.append("Lost to lower ranked team")
    
    # NEW v11: HEAD-TO-HEAD LOSSES IN ELIMS
    # This is HUGE - if they lost to another team in elims, they're exposed
    team_name = team_data.get('Team', '')
    team_h2h_losses = [
        h for h in h2h_losses 
        if h.get('loser', '').upper() == team_name.upper()
    ]
    if team_h2h_losses:
        score += 30  # Major penalty
        for loss in team_h2h_losses:
            flags.append(f"Lost to {loss.get('winner')} in {loss.get('round', 'elims')}")
    
    # CHOKES CLOSE GAMES: Bad clutch rate in close matches
    clutch = team_data.get('Clutch_Rate', 0.5)
    close_matches = team_data.get('Close_Matches', 0)
    if close_matches >= 3 and clutch < 0.35:
        score += 25
        flags.append(f"Chokes close games ({int(clutch*100)}%)")
    
    # NEW v11: EARLY ELIM EXIT
    # If a top seed loses in QF or SF, that's a red flag
    elim_exit = team_data.get('Elim_Exit_Round', 0)
    if rank <= 5 and elim_exit <= 2 and elim_exit > 0:
        score += 30
        exit_names = {1: 'R16', 2: 'QF', 3: 'SF', 4: 'Finals'}
        flags.append(f"Early elim exit ({exit_names.get(elim_exit, 'Early')})")
    
    # NEW v11: BAD ELIM RECORD
    # High rank but poor elim win rate = chokes under pressure
    elim_wins = team_data.get('Elim_Wins', 0)
    elim_losses = team_data.get('Elim_Losses', 0)
    elim_total = elim_wins + elim_losses
    if elim_total >= 2:
        elim_wr = elim_wins / elim_total
        if elim_wr < 0.4 and rank <= 8:
            score += 20
            flags.append(f"Bad elim record ({elim_wins}-{elim_losses})")
    
    # WEAK SCHEDULE: Beat bad teams to get high rank
    sp = team_data.get('SP', 0)
    if global_avg_sp > 0 and sp < global_avg_sp * 0.65:
        score += 18
        flags.append("Very weak schedule")
    
    # NO DOMINANT WINS: If you're top-ranked, you should have some blowouts
    if team_data.get('Wins', 0) >= 5 and team_data.get('Blowout_Wins', 0) == 0:
        score += 12
        flags.append("No dominant wins")
    
    # LOW SKILLS: High rank but robot doesn't perform in solo matches
    skills = team_data.get('Skills', 0)
    if rank <= 8 and skills < 30:
        score += 15
        flags.append(f"Low skills ({skills})")
    
    # DECLINING: Getting worse as event progresses
    if team_data.get('Trend', 0) <= -8:
        score += 15
        flags.append("Getting worse")
    
    # Threshold for fraud label depends on rank
    # Top 5 teams need more evidence to be called fraud
    threshold = 35 if rank <= 5 else 30
    return score >= threshold, flags, score


# =============================================================================
# MACHINE LEARNING MODEL TRAINING
# =============================================================================
# The ML model learns from past competitions to predict which teams will
# be successful. It's trained on features like:
# - Rank, Auto, SP (Strength of Schedule), WP (Win Points)
# - Average points, Standard deviation, Ceiling, Trend
# - Qual win rate, Elim win rate (NEW in v11)
#
# The target variable is "Was_Successful" - did the team reach finals
# or win a major award?
# =============================================================================

def train_model():
    """
    Trains the Random Forest machine learning model on historical data.
    
    NEW IN v11: 
    - Only uses CURRENT SEASON data (Push Back 2025-2026)
    - Includes Elim_Win_Rate as a feature
    
    The model learns patterns like:
    - Teams with high skills + high auto tend to succeed
    - Teams with high ceiling but low consistency might upset
    - Elim win rate is more predictive than qual win rate
    """
    # Check if we already have a trained model
    if os.path.exists(MODEL_FILE):
        print(f"✅ Model loaded: {MODEL_FILE}")
        return
    
    print("\n🧠 Training machine learning model...")
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    events = []
    
    try:
        # NEW v11: Only get CURRENT SEASON (Push Back)
        # This ensures we don't train on outdated data
        season_data = safe_request(
            "https://www.robotevents.com/api/v2/seasons?program[]=1", 
            headers
        )
        
        season_id = None
        for s in season_data.get('data', []):
            if "Push Back" in s['name']:
                season_id = s['id']
                print(f"   Found current season: {s['name']}")
                break
        
        # Find tournaments from this season
        if season_id:
            page = 1
            while len(events) < 30 and page < 8:
                url = f"https://www.robotevents.com/api/v2/events?season[]={season_id}&per_page=50&page={page}"
                data = safe_request(url, headers)
                
                if not data or not data.get('data'):
                    break
                
                for e in data['data']:
                    event_type = e.get('event_type') or ''
                    if event_type and "Tournament" in event_type:
                        events.append(e['sku'])
                
                page += 1
    except Exception as e:
        print(f"   Warning: Could not fetch season data: {e}")
    
    # Fallback events if API fails
    if not events:
        events = ["RE-V5RC-25-0179", "RE-V5RC-25-1516", "RE-V5RC-25-9998"]
    
    print(f"   Training on {min(25, len(events))} events...")
    
    # Collect training data from events
    all_rows = []
    
    for i, sku in enumerate(events[:25]):
        try:
            # Get event details
            event_data = safe_request(
                f"https://www.robotevents.com/api/v2/events?sku={sku}", 
                headers
            )
            if not event_data or not event_data.get('data'):
                continue
            
            event_id = event_data['data'][0]['id']
            divisions = event_data['data'][0].get('divisions', [{'id': 1}])
            
            stats = {}
            
            # Get rankings for each division
            for div in divisions:
                rank_data = safe_request(
                    f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/rankings?per_page=250",
                    headers
                )
                if rank_data:
                    for team in rank_data.get('data', []):
                        total_matches = team['wins'] + team['losses'] + team['ties']
                        if total_matches == 0:
                            continue
                        
                        stats[team['team']['id']] = {
                            'Rank': team['rank'],
                            'Auto': round(team['ap'] / total_matches, 2),
                            'SP': round(team['sp'] / total_matches, 1),
                            'WP': round(team['wp'] / total_matches, 2),
                            'Wins': team['wins'],
                            'Losses': team['losses'],
                            'Scores': [],
                            'Elim_Wins': 0,
                            'Elim_Losses': 0
                        }
            
            # Get match data for each division
            for div in divisions:
                match_data = safe_request(
                    f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/matches?per_page=250",
                    headers
                )
                if match_data:
                    for match in match_data.get('data', []):
                        match_name = match.get('name', '')
                        is_elim, _, _ = is_elim_match(match_name)
                        
                        alliances = match.get('alliances', [])
                        alliance_dict = {
                            a.get('color'): a 
                            for a in alliances
                        } if isinstance(alliances, list) else alliances
                        
                        r_score = alliance_dict.get('red', {}).get('score', 0)
                        b_score = alliance_dict.get('blue', {}).get('score', 0)
                        
                        # Record scores and elim results
                        for color in ['red', 'blue']:
                            score = alliance_dict.get(color, {}).get('score', 0)
                            opp_score = alliance_dict.get(
                                'blue' if color == 'red' else 'red', {}
                            ).get('score', 0)
                            won = score > opp_score
                            
                            if isinstance(score, (int, float)):
                                for t in alliance_dict.get(color, {}).get('teams', []):
                                    team_id = t['team']['id'] if 'team' in t else t.get('id')
                                    if team_id in stats:
                                        stats[team_id]['Scores'].append(score)
                                        
                                        # Track elim performance
                                        if is_elim:
                                            if won:
                                                stats[team_id]['Elim_Wins'] += 1
                                            else:
                                                stats[team_id]['Elim_Losses'] += 1
            
            # Get award winners (Tournament Champions only - CURRENT SEASON)
            award_data = safe_request(
                f"https://www.robotevents.com/api/v2/events/{event_id}/awards",
                headers
            )
            winners = set()
            if award_data:
                for award in award_data.get('data', []):
                    # Only count Tournament Champion - ignore old/other awards
                    if "Champion" in award.get('title', ''):
                        for winner in award.get('teamWinners', []):
                            winners.add(winner.get('team', {}).get('id'))
            
            # Build training examples
            for team_id, s in stats.items():
                if len(s['Scores']) < 3:
                    continue
                
                avg_pts = np.mean(s['Scores'])
                std_dev = np.std(s['Scores'])
                ceiling = np.percentile(s['Scores'], 90)
                
                # Calculate trend (improvement over event)
                trend = 0
                if len(s['Scores']) >= 4:
                    mid = len(s['Scores']) // 2
                    trend = np.mean(s['Scores'][mid:]) - np.mean(s['Scores'][:mid])
                
                # NEW v11: Elim win rate as feature
                elim_total = s['Elim_Wins'] + s['Elim_Losses']
                elim_wr = s['Elim_Wins'] / elim_total if elim_total > 0 else 0.5
                
                all_rows.append({
                    'Rank': s['Rank'],
                    'Auto': s['Auto'],
                    'SP': s['SP'],
                    'WP': s['WP'],
                    'Avg_Pts': avg_pts,
                    'Std_Dev': std_dev,
                    'Ceiling': ceiling,
                    'Trend': trend,
                    'Win_Rate': s['Wins'] / (s['Wins'] + s['Losses'] + 0.1),
                    'Elim_Win_Rate': elim_wr,  # NEW v11
                    'Was_Successful': 1 if team_id in winners else 0
                })
            
            print(f"   [{i+1}/{min(25, len(events))}] {sku}")
            
        except Exception as e:
            print(f"   Error processing {sku}: {e}")
            continue
    
    # Train the model
    if len(all_rows) >= 50:
        df = pd.DataFrame(all_rows).fillna(0)
        
        # Features used for prediction
        features = [
            'Rank', 'Auto', 'SP', 'WP', 
            'Avg_Pts', 'Std_Dev', 'Ceiling', 'Trend',
            'Win_Rate', 'Elim_Win_Rate'  # NEW v11: Elim win rate
        ]
        
        # Random Forest is good for this because:
        # - Handles non-linear relationships
        # - Resistant to overfitting
        # - Provides feature importance
        model = RandomForestClassifier(
            n_estimators=200,      # Number of trees
            max_depth=12,          # Prevent overfitting
            class_weight='balanced',  # Handle imbalanced classes
            random_state=42        # Reproducibility
        )
        
        model.fit(df[features], df['Was_Successful'])
        
        # Save model for future use
        joblib.dump({'model': model, 'features': features}, MODEL_FILE)
        print(f"✅ Trained on {len(df)} teams from {len(events[:25])} events")
        
    else:
        # Fallback: Create a simple model if we couldn't get enough data
        print("⚠️ Not enough data, using fallback model")
        
        # Generate synthetic training data
        df = pd.DataFrame([{
            'Rank': np.random.randint(1, 50),
            'Auto': np.random.uniform(0, 9),
            'SP': np.random.uniform(5, 45),
            'WP': np.random.uniform(0, 2),
            'Avg_Pts': np.random.uniform(25, 75),
            'Std_Dev': np.random.uniform(5, 25),
            'Ceiling': np.random.uniform(40, 100),
            'Trend': np.random.uniform(-15, 15),
            'Win_Rate': np.random.uniform(0.3, 0.9),
            'Elim_Win_Rate': np.random.uniform(0.3, 0.9),
            'Was_Successful': np.random.randint(0, 2)
        } for _ in range(500)])
        
        features = [
            'Rank', 'Auto', 'SP', 'WP',
            'Avg_Pts', 'Std_Dev', 'Ceiling', 'Trend',
            'Win_Rate', 'Elim_Win_Rate'
        ]
        
        model = RandomForestClassifier(n_estimators=100, class_weight='balanced')
        model.fit(df[features], df['Was_Successful'])
        joblib.dump({'model': model, 'features': features}, MODEL_FILE)


# =============================================================================
# SYNERGY CALCULATION
# =============================================================================
# Not all good teams make good partners! Synergy measures how well two
# teams would work TOGETHER in an alliance.
#
# Example: If your robot has weak auto, you want a partner with STRONG auto.
# Two robots with weak auto = bad alliance, even if both are "good" teams.
# =============================================================================

def calculate_synergy(my_stats, partner):
    """
    Calculates how well a potential partner would complement your team.
    
    Parameters:
        my_stats (dict): Your team's statistics
        partner (dict): Potential partner's statistics
    
    Returns:
        tuple: (synergy_score: int, reasons: list of strings)
    """
    score = 0
    reasons = []
    
    # COMBINED AUTO: Two strong autos is very powerful
    my_auto = my_stats.get('Auto', 0)
    partner_auto = partner.get('Auto', 0)
    combined_auto = my_auto + partner_auto
    
    if combined_auto >= 14:
        score += 25
        reasons.append("🔥 Elite combined auto")
    elif combined_auto >= 11:
        score += 15
        reasons.append("✅ Strong auto combo")
    elif combined_auto < 7:
        score -= 10
        reasons.append("⚠️ Weak auto together")
    
    # COVERS WEAKNESS: Partner is strong where you're weak
    if my_auto < 4.5 and partner_auto >= 6:
        score += 12
        reasons.append("Covers auto weakness")
    
    # COMBINED SCORING: High-scoring duo
    my_avg = my_stats.get('Avg_Pts', 0)
    partner_avg = partner.get('Avg_Pts', 0)
    if my_avg + partner_avg >= 85:
        score += 15
        reasons.append("💪 High scoring duo")
    
    # RELIABILITY: Low standard deviation = consistent scores
    if partner.get('Std_Dev', 15) < 10:
        score += 10
        reasons.append("🎯 Reliable")
    
    # TRUESKILL ELITE: Partner has proven high skill
    if partner.get('TrueSkill_Mu', 25) >= 30:
        score += 12
        reasons.append("🏆 TrueSkill elite")
    
    # SKILLS: Proves robot works in solo situations
    if partner.get('Skills', 0) >= 70:
        score += 10
        reasons.append(f"🎮 Skills: {partner.get('Skills', 0)}")
    
    # NEW v11: ELIM PERFORMER - proven to win when it matters
    if partner.get('Elim_Wins', 0) >= 2:
        score += 15
        reasons.append(f"🏆 Proven in elims ({partner.get('Elim_Wins')}W)")
    
    return score, reasons


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================
# This is the heart of the program. It:
# 1. Fetches all data from RobotEvents API
# 2. Calculates TrueSkill ratings for all teams
# 3. Computes OPR using linear algebra
# 4. Runs ML model predictions
# 5. Detects sleepers and frauds
# 6. Calculates synergy with user's team
# 7. Returns comprehensive analysis
# =============================================================================

def analyze_event(sku, api_key, my_team):
    """
    Performs comprehensive analysis of a VEX event.
    
    Parameters:
        sku (str): Event SKU (e.g., "RE-V5RC-25-1234")
        api_key (str): RobotEvents API key
        my_team (str): User's team number (e.g., "8568A")
    
    Returns:
        dict: Complete analysis including:
            - leaderboard: All teams ranked by AI score
            - sleepers: Underrated teams
            - frauds: Overrated teams
            - predictions: Predicted alliance selections
            - tierA/B/C: Pick recommendations
            - And much more...
    """
    global progress, event_cache
    progress = {'status': 'running', 'step': 'Starting...', 'percent': 0, 'detail': ''}
    
    # Train or load the ML model
    train_model()
    model_data = joblib.load(MODEL_FILE)
    model = model_data['model']
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # =========================================================================
    # STEP 1: Find the event
    # =========================================================================
    progress = {'status': 'running', 'step': 'Finding event...', 'percent': 5, 'detail': sku}
    
    event_data = safe_request(
        f"https://www.robotevents.com/api/v2/events?sku={sku}", 
        headers
    )
    
    if not event_data or not event_data.get('data'):
        progress = {'status': 'error', 'step': 'Event not found', 'percent': 0, 'detail': ''}
        return None
    
    event_id = event_data['data'][0]['id']
    event_name = event_data['data'][0]['name']
    divisions = event_data['data'][0].get('divisions', [{'id': 1}])
    
    print(f"\n📊 Analyzing: {event_name}")
    progress = {'status': 'running', 'step': 'Found event', 'percent': 10, 'detail': event_name}
    
    # Initialize data structures
    stats = {}           # Team statistics
    match_history = {}   # Match-by-match history for each team
    trueskill = {}       # TrueSkill ratings
    
    # =========================================================================
    # STEP 2: Get rankings
    # =========================================================================
    print("   [1/5] Getting rankings...")
    progress = {'status': 'running', 'step': 'Getting rankings...', 'percent': 15, 'detail': ''}
    
    for div in divisions:
        page = 1
        while True:
            rank_data = safe_request(
                f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/rankings?page={page}&per_page=250",
                headers
            )
            
            if not rank_data or not rank_data.get('data'):
                break
            
            for team in rank_data['data']:
                total_matches = team['wins'] + team['losses'] + team['ties']
                team_name = team['team']['name']
                
                stats[team_name] = {
                    'Team_ID': team['team']['id'],
                    'Rank': team['rank'],
                    'Record': f"{team['wins']}-{team['losses']}-{team['ties']}",
                    'Wins': team['wins'],
                    'Losses': team['losses'],
                    'Auto': round(team['ap'] / total_matches, 2) if total_matches > 0 else 0,
                    'WP': round(team['wp'] / total_matches, 2) if total_matches > 0 else 0,
                    'SP': round(team['sp'] / total_matches, 1) if total_matches > 0 else 0,
                    'Scores': [],
                    'Close_Wins': 0,
                    'Close_Matches': 0,
                    'Blowout_Wins': 0,
                    'Wins_vs_Higher': 0,
                    'Losses_to_Lower_This_Event': 0,
                    'Skills': 0,
                    'Elim_Wins': 0,      # NEW v11
                    'Elim_Losses': 0,    # NEW v11
                    'Elim_Exit_Round': 0 # NEW v11
                }
                
                match_history[team_name] = []
                trueskill[team_name] = TrueSkillRating()
            
            page += 1
    
    print(f"      Found {len(stats)} teams")
    progress = {'status': 'running', 'step': 'Rankings loaded', 'percent': 25, 'detail': f'{len(stats)} teams'}
    
    # =========================================================================
    # STEP 3: Analyze matches
    # =========================================================================
    print("   [2/5] Analyzing matches...")
    progress = {'status': 'running', 'step': 'Analyzing matches...', 'percent': 30, 'detail': ''}
    
    all_matches = []
    
    for div in divisions:
        page = 1
        while True:
            match_data = safe_request(
                f"https://www.robotevents.com/api/v2/events/{event_id}/divisions/{div['id']}/matches?page={page}&per_page=250",
                headers
            )
            
            if not match_data or not match_data.get('data'):
                break
            
            for match in match_data['data']:
                match_name = match.get('name', '')
                is_elim, elim_round, elim_weight = is_elim_match(match_name)
                
                alliances = match.get('alliances', [])
                alliance_dict = {
                    a.get('color'): a for a in alliances
                } if isinstance(alliances, list) else alliances
                
                r_score = alliance_dict.get('red', {}).get('score', 0)
                b_score = alliance_dict.get('blue', {}).get('score', 0)
                
                # Skip invalid matches
                if not isinstance(r_score, (int, float)) or not isinstance(b_score, (int, float)):
                    continue
                
                margin = abs(r_score - b_score)
                is_close = margin <= 12      # Close game
                is_blowout = margin >= 35    # Dominant win
                
                # Get team names from each alliance
                r_teams = [
                    t.get('team', {}).get('name') or t.get('name') 
                    for t in alliance_dict.get('red', {}).get('teams', [])
                ]
                b_teams = [
                    t.get('team', {}).get('name') or t.get('name') 
                    for t in alliance_dict.get('blue', {}).get('teams', [])
                ]
                r_teams = [t for t in r_teams if t]
                b_teams = [t for t in b_teams if t]
                
                all_matches.append({
                    'red': r_teams, 
                    'blue': b_teams, 
                    'r_score': r_score, 
                    'b_score': b_score,
                    'is_elim': is_elim
                })
                
                # UPDATE TRUESKILL RATINGS
                # Elim matches count MORE (1.5x multiplier)
                if r_score != b_score:
                    winners = r_teams if r_score > b_score else b_teams
                    losers = b_teams if r_score > b_score else r_teams
                    
                    w_ratings = [trueskill[t] for t in winners if t in trueskill]
                    l_ratings = [trueskill[t] for t in losers if t in trueskill]
                    
                    if w_ratings and l_ratings:
                        elim_multiplier = 1.5 if is_elim else 1.0
                        update_trueskill(w_ratings, l_ratings, margin * elim_multiplier)
                
                # Record detailed stats for each team
                for color, my_teams, my_score, opp_score, opp_teams in [
                    ('red', r_teams, r_score, b_score, b_teams),
                    ('blue', b_teams, b_score, r_score, r_teams)
                ]:
                    won = my_score > opp_score
                    
                    for team_name in my_teams:
                        if team_name not in stats:
                            continue
                        
                        s = stats[team_name]
                        s['Scores'].append(my_score)
                        
                        # Record match in history
                        match_history[team_name].append({
                            'name': match_name,
                            'score': my_score,
                            'opp_score': opp_score,
                            'won': won,
                            'is_elim': is_elim,
                            'elim_round': elim_round
                        })
                        
                        # NEW v11: Track elim performance
                        if is_elim:
                            if won:
                                s['Elim_Wins'] += 1
                            else:
                                s['Elim_Losses'] += 1
                            s['Elim_Exit_Round'] = max(s['Elim_Exit_Round'], elim_weight)
                        
                        # Track close games and clutch performance
                        if is_close:
                            s['Close_Matches'] += 1
                            if won:
                                s['Close_Wins'] += 1
                        
                        # Track blowout wins
                        if is_blowout and won:
                            s['Blowout_Wins'] += 1
                        
                        # Track wins vs higher ranked / losses to lower ranked
                        my_rank = s['Rank']
                        for opp in opp_teams:
                            if opp in stats:
                                opp_rank = stats[opp]['Rank']
                                if opp_rank < my_rank and won:
                                    s['Wins_vs_Higher'] += 1
                                elif opp_rank > my_rank + 3 and not won:
                                    s['Losses_to_Lower_This_Event'] += 1
            
            page += 1
    
    progress = {'status': 'running', 'step': 'Matches done', 'percent': 50, 'detail': f'{len(all_matches)} matches'}
    
    # =========================================================================
    # STEP 4: Calculate OPR (Offensive Power Rating)
    # =========================================================================
    # OPR uses linear algebra to separate individual contributions from
    # alliance scores. If we have many matches, we can solve a system of
    # equations to find each team's individual scoring rate.
    # =========================================================================
    print("   [3/5] Calculating OPR...")
    progress = {'status': 'running', 'step': 'Calculating OPR...', 'percent': 55, 'detail': ''}
    
    opr = {}
    
    if all_matches:
        team_list = list(stats.keys())
        team_idx = {t: i for i, t in enumerate(team_list)}
        n = len(team_list)
        
        if n > 0:
            # Build the system of equations
            # Each row is a match, each column is a team
            # A[i,j] = 1 if team j played in match i's alliance
            A = np.zeros((len(all_matches) * 2, n))
            b = np.zeros(len(all_matches) * 2)
            
            for i, match in enumerate(all_matches):
                # Red alliance
                for team in match['red']:
                    if team in team_idx:
                        A[i*2, team_idx[team]] = 1
                # Blue alliance
                for team in match['blue']:
                    if team in team_idx:
                        A[i*2+1, team_idx[team]] = 1
                
                b[i*2] = match['r_score']
                b[i*2+1] = match['b_score']
            
            try:
                # Solve using least squares (handles overdetermined systems)
                result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
                for team, idx in team_idx.items():
                    opr[team] = max(0, result[idx])  # OPR can't be negative
            except Exception as e:
                print(f"      OPR calculation failed: {e}")
    
    # =========================================================================
    # STEP 5: Get skills scores
    # =========================================================================
    print("   [4/5] Getting skills data...")
    progress = {'status': 'running', 'step': 'Skills data...', 'percent': 65, 'detail': ''}
    
    skills_data = safe_request(
        f"https://www.robotevents.com/api/v2/events/{event_id}/skills?per_page=250",
        headers
    )
    
    if skills_data:
        for sk in skills_data.get('data', []):
            team_name = sk.get('team', {}).get('name')
            if team_name in stats:
                # Keep the highest skills score (driver + programming combined)
                stats[team_name]['Skills'] = max(
                    stats[team_name]['Skills'], 
                    sk.get('score', 0)
                )
    
    # =========================================================================
    # STEP 6: Process all teams
    # =========================================================================
    print("   [5/5] Processing teams...")
    progress = {'status': 'running', 'step': 'Final calculations...', 'percent': 75, 'detail': ''}
    
    # Calculate global averages for context
    all_sp = [s['SP'] for s in stats.values() if s['SP'] > 0]
    global_avg_sp = np.mean(all_sp) if all_sp else 15
    
    # Calculate standard deviation thresholds for consistency labels
    all_stds = [np.std(s['Scores']) for s in stats.values() if len(s['Scores']) >= 3]
    std_low = np.percentile(all_stds, 30) if all_stds else 8
    std_high = np.percentile(all_stds, 70) if all_stds else 16
    
    processed = []
    
    for name, s in stats.items():
        has_matches = len(s['Scores']) >= 2
        
        # Calculate scoring statistics
        if has_matches:
            avg_pts = np.mean(s['Scores'])
            std_dev = np.std(s['Scores']) if len(s['Scores']) > 2 else 0
            ceiling = np.percentile(s['Scores'], 90) if len(s['Scores']) >= 3 else max(s['Scores'])
            floor = np.percentile(s['Scores'], 10) if len(s['Scores']) >= 3 else min(s['Scores'])
            
            # Trend: Are they improving or declining?
            trend = 0
            if len(s['Scores']) >= 4:
                mid = len(s['Scores']) // 2
                trend = np.mean(s['Scores'][mid:]) - np.mean(s['Scores'][:mid])
        else:
            # Pre-event estimates based on skills
            avg_pts = s['Skills'] * 0.5 if s['Skills'] > 0 else 30
            std_dev = 12
            ceiling = avg_pts * 1.2
            floor = avg_pts * 0.8
            trend = 0
        
        # Clutch rate: Win percentage in close games
        clutch_rate = s['Close_Wins'] / s['Close_Matches'] if s['Close_Matches'] > 0 else 0.5
        
        # Get TrueSkill and OPR
        ts = trueskill.get(name, TrueSkillRating())
        team_opr = opr.get(name, avg_pts * 0.5)
        
        # NEW v11: Get elim exit round
        exit_name, exit_round = get_elim_exit_round(match_history.get(name, []))
        
        # NEW v11: Elim win rate (separate from qual win rate!)
        elim_total = s['Elim_Wins'] + s['Elim_Losses']
        elim_win_rate = s['Elim_Wins'] / elim_total if elim_total > 0 else 0.5
        
        # Strength of Schedule (normalized 1-10)
        sos = 5.0
        if all_sp and max(all_sp) != min(all_sp):
            sos = round(1 + (s['SP'] - min(all_sp)) / (max(all_sp) - min(all_sp)) * 9, 1)
        
        # ML MODEL PREDICTION
        win_rate = s['Wins'] / (s['Wins'] + s['Losses'] + 0.1)
        try:
            X = [[
                s['Rank'], s['Auto'], s['SP'], s['WP'],
                avg_pts, std_dev, ceiling, trend,
                win_rate, elim_win_rate  # NEW v11
            ]]
            ml_raw = model.predict_proba(X)[0][1]  # Probability of success
        except:
            ml_raw = 0.5
        
        # CALCULATE OVERALL SCORE
        # Normalize each component to 0-1 range
        ts_norm = min(1, max(0, (ts.mu - 15) / 25))
        opr_norm = min(1, team_opr / 50)
        skills_norm = min(1, s['Skills'] / 120) if s['Skills'] > 0 else 0.3
        ceiling_norm = min(1, ceiling / 80)
        elim_norm = elim_win_rate if elim_total > 0 else 0.5
        
        # Weighted combination
        # NEW v11: Elim performance weighted at 15%
        overall = (
            ml_raw * 10 +           # ML prediction: 10%
            ts_norm * 20 +          # TrueSkill: 20%
            opr_norm * 10 +         # OPR: 10%
            skills_norm * 20 +      # Skills: 20%
            ceiling_norm * 10 +     # Ceiling: 10%
            clutch_rate * 10 +      # Clutch: 10%
            elim_norm * 15 +        # NEW v11: Elim win rate: 15%
            (1 - std_dev / 30) * 5  # Consistency: 5%
        )
        overall = max(0, min(100, overall))
        
        # NEW v11: MANUAL RATING OVERRIDE
        # If user has rated this team, blend their rating with AI
        if name in manual_ratings:
            user_rating = manual_ratings[name]
            user_score = user_rating * 10  # 1-10 -> 10-100
            # 60% user rating, 40% AI - human observation takes priority!
            overall = overall * 0.4 + user_score * 0.6
        
        # ASSIGN LABELS
        # Consistency label
        if not has_matches:
            play_style = "❓ Pre-Event"
        elif std_dev <= std_low:
            play_style = "🎯 Reliable"
        elif std_dev <= std_high:
            play_style = "⚖️ Balanced"
        else:
            play_style = "🎰 Wild Card"
        
        # Pressure label
        if s['Close_Matches'] < 2:
            pressure = "❓ Unknown"
        elif clutch_rate >= 0.6:
            pressure = "🧊 Clutch"
        elif clutch_rate >= 0.4:
            pressure = "➖ Average"
        else:
            pressure = "😰 Chokes"
        
        # Momentum label
        if trend >= 6:
            momentum = "🔥 Hot"
        elif trend >= 2:
            momentum = "📈 Up"
        elif trend <= -6:
            momentum = "📉 Down"
        else:
            momentum = "➡️ Steady"
        
        # NEW v11: Elim performance label
        if s['Elim_Wins'] >= 4:
            elim_label = "🏆 Champion"
        elif s['Elim_Wins'] >= 2:
            elim_label = "✅ Elim Winner"
        elif elim_total > 0 and elim_win_rate < 0.4:
            elim_label = "❌ Elim Choker"  # NEW v11: Chokes in elims flag!
        elif elim_total == 0:
            elim_label = "❓ No Elims"
        else:
            elim_label = "➖ Mixed"
        
        # FRAUD & SLEEPER DETECTION
        fraud_data = {
            'Team': name,
            'Rank': s['Rank'],
            'Clutch_Rate': clutch_rate,
            'Close_Matches': s['Close_Matches'],
            'SP': s['SP'],
            'Blowout_Wins': s['Blowout_Wins'],
            'Wins': s['Wins'],
            'Trend': trend,
            'Std_Dev': std_dev,
            'Losses_to_Lower_This_Event': s['Losses_to_Lower_This_Event'],
            'Skills': s['Skills'],
            'Ceiling': ceiling,
            'Avg_Pts': avg_pts,
            'Elim_Wins': s['Elim_Wins'],
            'Elim_Losses': s['Elim_Losses'],
            'Elim_Exit_Round': exit_round
        }
        is_fraud, fraud_flags, fraud_score = detect_fraud(fraud_data, global_avg_sp, head_to_head)
        
        sleeper_data = {
            'Rank': s['Rank'],
            'Ceiling': ceiling,
            'Avg_Pts': avg_pts,
            'Skills': s['Skills'],
            'Auto': s['Auto'],
            'Trend': trend,
            'Wins_vs_Higher': s['Wins_vs_Higher'],
            'TrueSkill_Mu': ts.mu,
            'Clutch_Rate': clutch_rate,
            'Close_Matches': s['Close_Matches'],
            'Blowout_Wins': s['Blowout_Wins'],
            'Elim_Wins': s['Elim_Wins']
        }
        sleeper_score, sleeper_reasons = calculate_sleeper_score(sleeper_data)
        
        # AUTO-GENERATED NOTES
        notes = []
        if s['Auto'] >= 7:
            notes.append("🔥 Elite auto")
        if s['Skills'] >= 80:
            notes.append(f"🎮 Strong skills ({s['Skills']})")
        if ts.mu >= 30:
            notes.append("🏆 High TrueSkill")
        if clutch_rate >= 0.65 and s['Close_Matches'] >= 3:
            notes.append("🧊 Clutch performer")
        if s['Wins_vs_Higher'] >= 2:
            notes.append(f"⚔️ Beat {s['Wins_vs_Higher']} higher ranked")
        if trend >= 8:
            notes.append("📈 Hot streak")
        if s['Elim_Wins'] >= 3:
            notes.append(f"🏆 {s['Elim_Wins']} elim wins!")
        if ceiling > avg_pts * 1.25:
            notes.append(f"🚀 High ceiling ({ceiling:.0f})")
        
        # Build team data object
        processed.append({
            'Team': name,
            'Team_ID': s['Team_ID'],
            'Rank': s['Rank'],
            'Record': s['Record'],
            'Auto': s['Auto'],
            'SP': round(s['SP'], 1),
            'Avg_Pts': round(avg_pts, 1),
            'Std_Dev': round(std_dev, 1),
            'Ceiling': round(ceiling, 1),
            'Floor': round(floor, 1),
            'Trend': round(trend, 1),
            'OPR': round(team_opr, 1),
            'Skills': s['Skills'],
            'TrueSkill_Mu': round(ts.mu, 1),
            'TrueSkill_Sigma': round(ts.sigma, 1),
            'SOS_Rating': sos,
            'Overall_Score': round(overall, 1),
            'Overall_Grade': '',  # Filled in below
            'Play_Style': play_style,
            'Pressure': pressure,
            'Momentum': momentum,
            'Clutch_Rate': round(clutch_rate, 2),
            'Close_Matches': s['Close_Matches'],
            'Blowout_Wins': s['Blowout_Wins'],
            'Wins_vs_Higher': s['Wins_vs_Higher'],
            # NEW v11 fields
            'Elim_Wins': s['Elim_Wins'],
            'Elim_Losses': s['Elim_Losses'],
            'Elim_Record': f"{s['Elim_Wins']}-{s['Elim_Losses']}" if elim_total > 0 else '-',
            'Elim_Exit': exit_name or '-',
            'Elim_Label': elim_label,
            'Manual_Rating': manual_ratings.get(name),
            # Detection results
            'Is_Fraud': is_fraud,
            'Fraud_Flags': fraud_flags,
            'Fraud_Score': fraud_score,
            'Sleeper_Score': sleeper_score,
            'Sleeper_Reasons': sleeper_reasons,
            'Is_Sleeper': sleeper_score >= 40,
            # Notes
            'Auto_Notes': notes,
            'Manual_Note': team_notes.get(name, ''),
            'Matches': match_history.get(name, [])
        })
    
    # Assign grades based on overall scores
    all_scores = [p['Overall_Score'] for p in processed]
    for p in processed:
        p['Overall_Grade'] = get_grade(p['Overall_Score'], all_scores)
    
    # =========================================================================
    # STEP 7: Calculate synergy and pick recommendations
    # =========================================================================
    
    # Find user's team data
    my_stats = {'Rank': 999, 'Auto': 0, 'Avg_Pts': 0, 'Overall_Score': 0}
    if my_team:
        my_upper = my_team.upper().strip()
        for p in processed:
            if p['Team'].upper().strip() == my_upper:
                my_stats = p.copy()
                break
    
    # Calculate synergy with each potential partner
    for p in processed:
        syn_score, syn_reasons = calculate_synergy(my_stats, p)
        p['Synergy_Score'] = syn_score
        p['Synergy_Reasons'] = syn_reasons
        
        # Determine availability (can you pick this team?)
        my_rank = my_stats.get('Rank', 999)
        if my_rank >= 999:
            p['Availability'] = "Available"
            p['Can_Pick'] = True
            avail_bonus = 0
        elif p['Rank'] < my_rank:
            p['Availability'] = "Picks before you"
            p['Can_Pick'] = False
            avail_bonus = -100
        elif p['Rank'] <= my_rank + 3 and p['Overall_Score'] >= 55:
            p['Availability'] = "Might be taken"
            p['Can_Pick'] = True
            avail_bonus = 0
        else:
            p['Availability'] = "Available"
            p['Can_Pick'] = True
            avail_bonus = 5
        
        # Calculate partner score (for pick recommendations)
        partner_base = p['Overall_Score'] * 0.4 + syn_score * 0.3 + avail_bonus
        
        # Bonuses and penalties
        if p['Is_Sleeper']:
            partner_base += 15  # Sleeper bonus
        if p['Is_Fraud']:
            partner_base -= 25  # Fraud penalty (bigger in v11)
        if p['Elim_Wins'] >= 2:
            partner_base += 10  # Elim winner bonus
        
        p['Partner_Score'] = round(partner_base + (80 / (p['Rank'] + 1)) * 0.15, 1)
    
    # Determine which captains might pick user's team
    who_wants = []
    if my_stats.get('Rank', 999) < 999:
        for cap in [p for p in processed if p['Rank'] <= 8]:
            if cap['Team'].upper() == my_team.upper():
                continue
            
            cap_stats = {
                'Auto': cap['Auto'],
                'Avg_Pts': cap['Avg_Pts'],
                'Std_Dev': cap.get('Std_Dev', 10)
            }
            
            # Find who this captain would most likely pick
            best, best_score = None, -999
            for cand in processed:
                if cand['Rank'] <= cap['Rank']:
                    continue
                syn, _ = calculate_synergy(cap_stats, cand)
                score = cand['Overall_Score'] * 0.5 + syn * 0.5
                if score > best_score:
                    best_score, best = score, cand['Team']
            
            if best and best.upper() == my_team.upper():
                who_wants.append({
                    'Captain': cap['Team'],
                    'Captain_Rank': cap['Rank']
                })
    
    # =========================================================================
    # STEP 8: Build final outputs
    # =========================================================================
    
    # Leaderboard (frauds excluded)
    leaderboard = sorted(
        [p for p in processed if not p['Is_Fraud']],
        key=lambda x: x['Overall_Score'],
        reverse=True
    )
    ai_top10 = leaderboard[:10]
    
    # Sleepers list
    sleepers = sorted(
        [p for p in processed if p['Is_Sleeper']],
        key=lambda x: x['Sleeper_Score'],
        reverse=True
    )[:10]
    
    # Pickable teams (frauds excluded, sorted by partner score)
    pickable = sorted(
        [p for p in processed if p.get('Can_Pick', False) and not p['Is_Fraud']],
        key=lambda x: x['Partner_Score'],
        reverse=True
    )
    
    # Alliance predictions
    predictions = []
    available = [p['Team'] for p in processed if p['Rank'] > 8]
    team_lookup = {p['Team']: p for p in processed}
    
    for cap_rank in range(1, 9):
        cap = next((p for p in processed if p['Rank'] == cap_rank), None)
        if not cap:
            continue
        
        best_pick, best_score = None, -999
        
        for team in available:
            cand = team_lookup.get(team)
            if not cand or cand['Is_Fraud']:
                continue
            
            cap_stats = {
                'Auto': cap['Auto'],
                'Avg_Pts': cap['Avg_Pts'],
                'Std_Dev': cap.get('Std_Dev', 10)
            }
            syn, _ = calculate_synergy(cap_stats, cand)
            score = cand['Overall_Score'] * 0.5 + syn * 0.4 + cand['Sleeper_Score'] * 0.1
            
            if score > best_score:
                best_score, best_pick = score, team
        
        if best_pick:
            predictions.append({
                'captain': cap['Team'],
                'captain_rank': cap_rank,
                'pick': best_pick,
                'pick_rank': team_lookup[best_pick]['Rank']
            })
            available.remove(best_pick)
    
    # Frauds list
    frauds = [p for p in processed if p['Is_Fraud']]
    
    # Save to cache
    event_cache[sku] = {
        'event_name': event_name,
        'my_team': my_team,
        'timestamp': time.time()
    }
    save_file(CACHE_FILE, event_cache)
    
    print(f"   ✅ Done! {len(processed)} teams, {len(frauds)} frauds, {len(sleepers)} sleepers")
    progress = {'status': 'complete', 'step': 'Done!', 'percent': 100, 'detail': ''}
    
    # Return complete analysis
    return {
        'eventName': event_name,
        'myRank': my_stats.get('Rank', 999),
        'myTeamData': my_stats,
        'totalTeams': len(processed),
        'whoWantsYou': who_wants,
        'aiTop10': ai_top10,
        'sleepers': sleepers,
        'alliancePredictions': predictions,
        'tierA': pickable[:5],
        'tierB': pickable[5:12],
        'tierC': pickable[12:20],
        'frauds': frauds,
        'recommended': pickable[0] if pickable else None,
        'allPickable': pickable,
        'allTeams': processed,
        'leaderboard': leaderboard,
        'picked': live_state['picked'],
        'bracket': live_state['bracket'],
        'manualRatings': manual_ratings,
        'headToHead': head_to_head
    }


# =============================================================================
# FLASK WEB SERVER ROUTES
# =============================================================================
# These are the API endpoints that the frontend (HTML/JavaScript) calls.
# Each route handles a specific action like analyzing an event, saving
# a rating, marking a team as picked, etc.
# =============================================================================

@app.route('/')
def index():
    """Serves the main HTML page"""
    try:
        return Response(
            open('index.html', encoding='utf-8').read(), 
            mimetype='text/html'
        )
    except:
        return "index.html not found", 404


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """
    Main analysis endpoint - analyzes an event.
    
    POST body:
        {apiKey, eventSku, myTeam}
    
    Returns:
        Complete analysis JSON
    """
    global cached_data
    req = request.json
    
    api_key = req.get('apiKey') or API_KEY
    sku = req.get('eventSku')
    my_team = req.get('myTeam', '')
    
    if not sku:
        return jsonify({'error': 'Need SKU'}), 400
    
    try:
        result = analyze_event(sku, api_key, my_team)
        if not result:
            return jsonify({'error': 'No data'}), 404
        
        # Cache for refresh
        cached_data = {
            'sku': sku,
            'api_key': api_key,
            'my_team': my_team,
            'result': result
        }
        return jsonify(result)
        
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """Re-runs analysis with cached settings for quick update"""
    global cached_data
    
    if not cached_data.get('sku'):
        return jsonify({'error': 'Run analysis first'}), 400
    
    try:
        result = analyze_event(
            cached_data['sku'],
            cached_data['api_key'],
            cached_data['my_team']
        )
        if not result:
            return jsonify({'error': 'Refresh failed'}), 404
        
        cached_data['result'] = result
        return jsonify(result)
        
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/progress')
def api_progress():
    """Returns current analysis progress for the loading bar"""
    return jsonify(progress)


@app.route('/api/notes', methods=['POST'])
def save_note():
    """
    Saves a scouting note for a team.
    
    POST body:
        {team, note}
    """
    req = request.json
    team = req.get('team')
    note = req.get('note', '')
    
    if team:
        team_notes[team] = note
        save_file(NOTES_FILE, team_notes)
        return jsonify({'success': True})
    
    return jsonify({'error': 'No team'}), 400


# =============================================================================
# NEW v11: MANUAL RATING ENDPOINT
# =============================================================================

@app.route('/api/rate', methods=['POST'])
def rate_team():
    """
    NEW v11: Saves a manual 1-10 rating for a team.
    
    This allows users to override the AI score based on what they
    observe at the competition. Rating of 0 removes the rating.
    
    POST body:
        {team, rating}  (rating is 1-10, or 0 to remove)
    """
    global manual_ratings
    req = request.json
    
    team = req.get('team')
    rating = req.get('rating')
    
    if team and rating is not None:
        if rating == 0:
            # Remove rating
            manual_ratings.pop(team, None)
        else:
            # Save rating (clamp to 1-10)
            manual_ratings[team] = max(1, min(10, int(rating)))
        
        save_file(RATINGS_FILE, manual_ratings)
        return jsonify({'success': True, 'ratings': manual_ratings})
    
    return jsonify({'error': 'Need team and rating'}), 400


# =============================================================================
# NEW v11: HEAD-TO-HEAD TRACKER ENDPOINTS
# =============================================================================

@app.route('/api/h2h', methods=['POST'])
def add_h2h():
    """
    NEW v11: Records a head-to-head result from eliminations.
    
    This is CRITICAL for fraud detection - if team A beat team B
    in elims, team B shouldn't be ranked above team A!
    
    POST body:
        {winner, loser, round}  (round is "QF", "SF", "Finals", etc.)
    """
    global head_to_head
    req = request.json
    
    winner = req.get('winner')
    loser = req.get('loser')
    round_name = req.get('round', 'Elims')
    
    if winner and loser:
        head_to_head.append({
            'winner': winner,
            'loser': loser,
            'round': round_name
        })
        save_file(H2H_FILE, head_to_head)
        return jsonify({'success': True, 'h2h': head_to_head})
    
    return jsonify({'error': 'Need winner and loser'}), 400


@app.route('/api/h2h/clear', methods=['POST'])
def clear_h2h():
    """Clears all head-to-head records (for new event)"""
    global head_to_head
    head_to_head = []
    save_file(H2H_FILE, head_to_head)
    return jsonify({'success': True, 'h2h': []})


@app.route('/api/ratings', methods=['GET'])
def get_ratings():
    """Returns current manual ratings and H2H records"""
    return jsonify({
        'ratings': manual_ratings,
        'h2h': head_to_head
    })


# =============================================================================
# LIVE TRACKING ENDPOINTS
# =============================================================================

@app.route('/api/pick', methods=['POST'])
def api_pick():
    """Marks a team as picked during alliance selection"""
    team = request.json.get('team')
    if team and team not in live_state['picked']:
        live_state['picked'].append(team)
    return jsonify({'picked': live_state['picked']})


@app.route('/api/unpick', methods=['POST'])
def api_unpick():
    """Unmarks a team as picked (undo)"""
    team = request.json.get('team')
    if team in live_state['picked']:
        live_state['picked'].remove(team)
    return jsonify({'picked': live_state['picked']})


@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Resets all picks (start over)"""
    live_state['picked'] = []
    live_state['bracket'] = []
    return jsonify({'picked': []})


@app.route('/api/bracket', methods=['POST'])
def api_bracket():
    """Saves elimination bracket data"""
    live_state['bracket'] = request.json.get('bracket', [])
    return jsonify({'bracket': live_state['bracket']})


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    # Print startup banner
    print("\n" + "="*60)
    print("🤖 VEX SCOUT v11 - EYE TEST EDITION")
    print("="*60)
    print("NEW FEATURES:")
    print("  ✅ Manual ratings (YOU rate teams 1-10)")
    print("  ✅ Head-to-head tracking (who beat who in elims)")
    print("  ✅ Elim performance weighted higher")
    print("  ✅ 'Chokes in elims' detection")
    print("  ✅ Current season awards only")
    print("  ✅ Better fraud detection with H2H data")
    print("="*60)
    print("🌐 Open http://localhost:5000 in your browser")
    print("="*60 + "\n")
    
    # Start the web server
    app.run(debug=True, port=5000)