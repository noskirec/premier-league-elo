import asyncio
from typing import Dict, List
import nest_asyncio
import aiohttp
from understat import Understat

nest_asyncio.apply()


async def _get_season_results(season_year: int) -> list:
    async with aiohttp.ClientSession() as session:
        u = Understat(session)
        return await u.get_league_results("EPL", season_year)


async def _get_match_shots(match_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        u = Understat(session)
        return await u.get_match_shots(match_id)


async def _get_match_roster(match_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        u = Understat(session)
        return await u.get_match_roster(match_id)


def get_season_results(season_year: int) -> list:
    """
    Return list of match result dicts for an EPL season.
    season_year is the calendar start year (e.g. 2021 for 2021-22 season).
    Each dict includes keys: 'id', 'datetime', 'h' (home info dict), 'a' (away info dict).
    """
    return asyncio.run(_get_season_results(season_year))


def get_match_shots(match_id: int) -> dict:
    """
    Return {'h': [...shots...], 'a': [...shots...]} where each shot includes:
    'id', 'minute', 'xG', 'player', 'player_id'.
    """
    return asyncio.run(_get_match_shots(match_id))


def get_match_roster(match_id: int) -> dict:
    """
    Return {'h': [...players...], 'a': [...players...]} where each player includes:
    'id', 'player', 'time' (minutes played), 'position' ('Sub' or position string).
    """
    return asyncio.run(_get_match_roster(match_id))


def parse_starters(roster: dict, team_key: str) -> List[str]:
    """Return list of 'us_{player_id}' for players who were not substitutes."""
    return [
        f"us_{p['id']}"
        for p in roster.get(team_key, [])
        if p.get('position') != 'Sub'
    ]


def parse_substitutions(roster: dict, team_key: str, team_id: str,
                        total_minutes: int = 90) -> List[Dict]:
    """
    Approximate substitution events from roster.
    Understat provides minutes played rather than exact sub timing.
    A starter with time_played < total_minutes was subbed off at minute = time_played.
    The matching sub came on at approximately (total_minutes - sub_time_played).
    Pairing is best-effort within +-5 minutes. Minutes are approximate.
    """
    players = roster.get(team_key, [])
    starters = [p for p in players if p.get('position') != 'Sub']
    subs = [p for p in players if p.get('position') == 'Sub']

    substitutions = []
    used = set()
    for starter in starters:
        played = int(starter.get('time', total_minutes))
        if played >= total_minutes - 1:
            continue
        for sub in subs:
            if sub['id'] in used:
                continue
            sub_played = int(sub.get('time', 0))
            came_on_approx = total_minutes - sub_played
            if abs(came_on_approx - played) <= 5:
                substitutions.append({
                    'minute': played,
                    'player_off_id': f"us_{starter['id']}",
                    'player_on_id': f"us_{sub['id']}",
                    'team_id': team_id
                })
                used.add(sub['id'])
                break
    return substitutions


def parse_shots(shots: dict, team_key: str, team_id: str, match_id: int) -> List[Dict]:
    """
    Return list of shot dicts with keys: event_id, minute, xg, shooting_team_id.
    shooter_player_id is intentionally omitted — fbref and understat use different
    player ID namespaces and the field is not used in ELO calculation.
    """
    result = []
    for i, shot in enumerate(shots.get(team_key, [])):
        xg = float(shot.get('xG', 0))
        if xg <= 0:
            continue
        result.append({
            'event_id': f"us_{match_id}_{team_key}_{i}",
            'minute': int(shot.get('minute', 0)),
            'xg': xg,
            'shooting_team_id': team_id,
        })
    return result
