import soccerdata as sd
from typing import Dict, List

_ALIASES = {
    'wolverhampton wanderers': 'wolves',
    'brighton & hove albion': 'brighton',
    'brighton and hove albion': 'brighton',
    'west ham united': 'west ham',
    'tottenham hotspur': 'tottenham',
    'nottingham forest': "nott'm forest",
    'newcastle united': 'newcastle',
    'leicester city': 'leicester',
    'sheffield united': 'sheffield utd',
    'luton town': 'luton',
    'manchester united': 'manchester utd',
    'afc bournemouth': 'bournemouth',
    'queens park rangers': 'qpr',
}


def normalize_team_name(name: str) -> str:
    """Normalize a team name for cross-source matching (fbref <-> understat)."""
    s = name.lower().strip()
    for suffix in (' fc', ' afc', ' f.c.'):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    if s.startswith('afc '):
        s = s[4:]
    return _ALIASES.get(s, s)


def _build_sub_events_from_events(events_df, game_id, home_team, away_team,
                                   home_starters, away_starters) -> List[Dict]:
    """
    Extract exact substitution minutes from match events DataFrame.
    Returns list of sub dicts or empty list if events unavailable.
    """
    gev = events_df[events_df['game'] == game_id] if 'game' in events_df.columns else events_df.iloc[0:0]
    sub_rows = gev[gev['type'].str.contains('Sub', case=False, na=False)]
    if sub_rows.empty:
        return []

    substitutions = []
    all_starters = {pid: (home_team if pid in home_starters else away_team)
                    for pid in home_starters + away_starters}

    for _, row in sub_rows.iterrows():
        minute = int(row.get('minute', 0) or 0)
        player_off = str(row.get('player', ''))
        player_on = str(row.get('notes', ''))  # fbref often puts the incoming player in notes
        team = str(row.get('team', ''))

        off_pid = f"fb_{player_off}"
        on_pid = f"fb_{player_on}" if player_on and player_on != 'nan' else None

        if off_pid in all_starters and on_pid:
            substitutions.append({
                'minute': minute,
                'player_off_id': off_pid,
                'player_on_id': on_pid,
                'team_id': team,
            })

    return substitutions


def _build_sub_events_from_minutes(starters_df, bench_df, team_name) -> List[Dict]:
    """
    Approximate substitutions from minutes_played when events data is unavailable.
    Starter subbed off at minute = their minutes_played.
    Matches bench player by closest (90 - bench_minutes) to starter minutes.
    """
    substitutions = []
    used_bench = set()

    for _, s_row in starters_df.iterrows():
        mins = int(s_row.get('minutes_played', 90) or 90)
        if mins >= 89:
            continue
        for _, b_row in bench_df.iterrows():
            bname = str(b_row['player'])
            if bname in used_bench:
                continue
            b_mins = int(b_row.get('minutes_played', 0) or 0)
            came_on = 90 - b_mins
            if abs(came_on - mins) <= 5:
                substitutions.append({
                    'minute': mins,
                    'player_off_id': f"fb_{s_row['player']}",
                    'player_on_id': f"fb_{bname}",
                    'team_id': team_name,
                })
                used_bench.add(bname)
                break

    return substitutions


def get_season_lineups(season_year: int) -> Dict[str, Dict]:
    """
    Pre-fetch all lineup data for one EPL season from fbref via soccerdata.
    soccerdata caches results to disk on first run; subsequent calls are instant.

    Returns dict keyed by "{date}|{normalize(home)}|{normalize(away)}".
    Each value: {home_starters, away_starters, substitutions, player_names}
    where player IDs are "fb_{player_name}".

    season_year: calendar start year, e.g. 2022 for the 2022-23 season.
    """
    fbref = sd.FBref(leagues="ENG-Premier League", seasons=season_year)

    sched = fbref.read_schedule().reset_index()
    lineup_df = fbref.read_lineup().reset_index()

    # Try to get events for exact substitution minutes; fall back gracefully
    try:
        events_df = fbref.read_events().reset_index()
    except Exception:
        events_df = None

    result = {}

    for _, game_row in sched.iterrows():
        game_id = game_row['game']
        date = str(game_row['date'])[:10]
        home = str(game_row['home_team'])
        away = str(game_row['away_team'])
        key = f"{date}|{normalize_team_name(home)}|{normalize_team_name(away)}"

        gdf = lineup_df[lineup_df['game'] == game_id]
        if gdf.empty:
            continue

        home_starters, away_starters, player_names = [], [], {}

        for team_name, is_home in [(home, True), (away, False)]:
            tdf = gdf[gdf['team'] == team_name]
            if tdf.empty:
                continue

            for _, row in tdf.iterrows():
                pid = f"fb_{row['player']}"
                player_names[pid] = str(row['player'])

            starters_df = tdf[tdf['is_starter'].astype(bool)]
            if is_home:
                home_starters = [f"fb_{r['player']}" for _, r in starters_df.iterrows()]
            else:
                away_starters = [f"fb_{r['player']}" for _, r in starters_df.iterrows()]

        # Build substitutions — prefer exact minutes from events, fall back to minutes_played
        if events_df is not None and not events_df.empty:
            substitutions = _build_sub_events_from_events(
                events_df, game_id, home, away, home_starters, away_starters
            )
        else:
            substitutions = []

        if not substitutions:
            # Fallback: infer from minutes_played in lineup
            for team_name in [home, away]:
                tdf = gdf[gdf['team'] == team_name]
                starters_df = tdf[tdf['is_starter'].astype(bool)]
                bench_df = tdf[~tdf['is_starter'].astype(bool)]
                substitutions += _build_sub_events_from_minutes(starters_df, bench_df, team_name)

        result[key] = {
            'home_starters': home_starters,
            'away_starters': away_starters,
            'substitutions': substitutions,
            'player_names': player_names,
        }

    return result
