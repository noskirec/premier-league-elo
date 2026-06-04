from typing import Dict, List
import pandas as pd
from statsbombpy import sb


PL_COMPETITION_ID = 2


def get_available_seasons() -> pd.DataFrame:
    """Return DataFrame of PL seasons available in StatsBomb open data."""
    comps = sb.competitions()
    pl = comps[comps['competition_id'] == PL_COMPETITION_ID]
    return pl[['season_id', 'season_name']].reset_index(drop=True)


def get_matches(season_id: int) -> pd.DataFrame:
    return sb.matches(competition_id=PL_COMPETITION_ID, season_id=season_id)


def get_starters(match_id: int) -> Dict[str, List[str]]:
    """Return {team_name: ['sb_{player_id}', ...]} for the starting 11 of each team."""
    lineups = sb.lineups(match_id=match_id)
    return {
        team_name: [f"sb_{pid}" for pid in df['player_id'].tolist()]
        for team_name, df in lineups.items()
    }


def get_substitutions(match_id: int, home_team: str, away_team: str) -> List[Dict]:
    """
    Return list of substitution dicts with keys:
    minute, player_off_id, player_on_id, team_id.
    team_id is the team name string (consistent with home_team/away_team keys).
    """
    events = sb.events(match_id=match_id)
    subs_df = events[events['type'] == 'Substitution']
    result = []
    for _, row in subs_df.iterrows():
        replacement = row.get('substitution_replacement')
        if isinstance(replacement, dict):
            player_on_id = f"sb_{replacement['id']}"
        else:
            player_on_id = f"sb_{row.get('substitution_replacement_id', '')}"
        result.append({
            'minute': int(row['minute']),
            'player_off_id': f"sb_{row['player_id']}",
            'player_on_id': player_on_id,
            'team_id': str(row['team'])
        })
    return result


def get_shots(match_id: int) -> List[Dict]:
    """
    Return list of shot dicts with keys:
    event_id, minute, xg, shooting_team_id, shooter_player_id.
    """
    events = sb.events(match_id=match_id)
    shots_df = events[events['type'] == 'Shot']
    result = []
    for _, row in shots_df.iterrows():
        xg = row.get('shot_statsbomb_xg')
        if pd.isna(xg):
            continue
        result.append({
            'event_id': f"sb_{row['id']}",
            'minute': int(row['minute']),
            'xg': float(xg),
            'shooting_team_id': str(row['team']),
            'shooter_player_id': f"sb_{row['player_id']}"
        })
    return result


def get_player_names(match_id: int) -> Dict[str, str]:
    """Return {'sb_{player_id}': 'Player Name'} for all players in a match."""
    lineups = sb.lineups(match_id=match_id)
    names = {}
    for _, df in lineups.items():
        for _, row in df.iterrows():
            names[f"sb_{row['player_id']}"] = row['player_name']
    return names
