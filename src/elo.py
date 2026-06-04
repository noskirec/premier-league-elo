from typing import Dict, List, Tuple


BASELINE_RATING = 1000.0


def get_players_on_pitch(
    starters: List[str],
    substitutions: List[Dict],
    minute: int
) -> List[str]:
    on_pitch = list(starters)
    for sub in substitutions:
        if sub['minute'] <= minute:
            if sub['player_off_id'] in on_pitch:
                on_pitch.remove(sub['player_off_id'])
            if sub['player_on_id'] not in on_pitch:
                on_pitch.append(sub['player_on_id'])
    return on_pitch


def apply_xg_event(
    ratings: Dict[str, float],
    attacking_players: List[str],
    defending_players: List[str],
    xg_value: float
) -> Dict[str, float]:
    updated = dict(ratings)
    for pid in attacking_players:
        updated[pid] = updated.get(pid, BASELINE_RATING) + xg_value
    for pid in defending_players:
        updated[pid] = updated.get(pid, BASELINE_RATING) - xg_value
    return updated


def process_match(
    ratings: Dict[str, float],
    home_team_id: str,
    away_team_id: str,
    home_starters: List[str],
    away_starters: List[str],
    substitutions: List[Dict],
    xg_events: List[Dict]
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Process all xG events for one match.
    xg_events items must have keys: minute (int), xg (float), shooting_team_id (str).
    substitutions items must have keys: minute, player_off_id, player_on_id, team_id.
    Returns (updated_ratings, per_player_delta_this_match).
    """
    ratings_before = dict(ratings)
    current = dict(ratings)
    home_subs = [s for s in substitutions if s['team_id'] == home_team_id]
    away_subs = [s for s in substitutions if s['team_id'] == away_team_id]

    for event in sorted(xg_events, key=lambda e: e['minute']):
        if event['shooting_team_id'] == home_team_id:
            attacking = get_players_on_pitch(home_starters, home_subs, event['minute'])
            defending = get_players_on_pitch(away_starters, away_subs, event['minute'])
        else:
            attacking = get_players_on_pitch(away_starters, away_subs, event['minute'])
            defending = get_players_on_pitch(home_starters, home_subs, event['minute'])
        current = apply_xg_event(current, attacking, defending, event['xg'])

    all_players = set(
        home_starters + away_starters + [s['player_on_id'] for s in substitutions]
    )
    deltas = {
        pid: current.get(pid, BASELINE_RATING) - ratings_before.get(pid, BASELINE_RATING)
        for pid in all_players
    }
    return current, deltas
