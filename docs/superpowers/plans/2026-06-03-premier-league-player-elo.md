# Premier League Player ELO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public GitHub project that calculates and visualizes Premier League player ELO ratings based on xG shot events over 5 seasons, deployed as a static site on GitHub Pages.

**Architecture:** Jupyter notebooks orchestrate pure-Python modules that fetch match/xG data (StatsBomb open data + understat.com), calculate per-player ELO, write results to SQLite, and generate a self-contained `index.html`. StatsBomb is used where available (~3 PL seasons of open data); understat fills remaining seasons.

**Tech Stack:** Python 3.10+, statsbombpy, understat, aiohttp, nest-asyncio, pandas, plotly, sqlite3 (stdlib), pytest

---

## File Map

| File | Responsibility |
|---|---|
| `src/db.py` | SQLite schema creation and CRUD operations |
| `src/elo.py` | Pure ELO logic: lineup tracking, xG application per match |
| `src/statsbomb_loader.py` | Fetch matches/lineups/shots from StatsBomb open data |
| `src/understat_loader.py` | Fetch matches/lineups/shots from understat.com |
| `src/site_builder.py` | Generate leaderboard HTML, sparklines, Plotly detail view, full index.html |
| `tests/test_db.py` | Tests for db.py |
| `tests/test_elo.py` | Tests for elo.py |
| `tests/test_site_builder.py` | Tests for site_builder.py |
| `notebooks/01_fetch_data.ipynb` | Fetch and cache raw data to `data/raw/` |
| `notebooks/02_calculate_elo.ipynb` | Run ELO pipeline, write results to `data/elo.db` |
| `notebooks/03_build_site.ipynb` | Query DB, generate `index.html` |

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `data/.gitkeep`
- Create: `data/raw/.gitkeep`
- Create: `notebooks/.gitkeep`

- [ ] **Step 1: Create `requirements.txt`**

```
statsbombpy>=1.0.3
understat>=0.2.1
aiohttp>=3.9.0
nest-asyncio>=1.6.0
pandas>=2.0.0
plotly>=5.18.0
pytest>=7.4.0
jupyter>=1.0.0
ipykernel>=6.0.0
```

- [ ] **Step 2: Create `.gitignore`**

```
data/raw/
__pycache__/
*.pyc
.ipynb_checkpoints/
.env
```

Note: `data/elo.db` is intentionally NOT gitignored — it is committed so visitors can download it.

- [ ] **Step 3: Create directories and empty init files**

Run in `C:\Users\Owner\Documents\premier-league-elo`:

```powershell
New-Item -ItemType Directory -Force src, tests, notebooks, data/raw | Out-Null
New-Item -Force src/__init__.py, tests/__init__.py | Out-Null
New-Item -Force data/.gitkeep, data/raw/.gitkeep, notebooks/.gitkeep | Out-Null
```

- [ ] **Step 4: Install dependencies**

```powershell
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore src/__init__.py tests/__init__.py data/.gitkeep data/raw/.gitkeep notebooks/.gitkeep
git commit -m "feat: project scaffolding"
git push origin main
```

---

### Task 2: Database module

**Files:**
- Create: `src/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db.py`:

```python
import os
import tempfile
import pytest
from src.db import (
    create_db, upsert_player, insert_match, insert_xg_event,
    upsert_player_rating, get_current_ratings, get_player_history
)


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    conn = create_db(path)
    yield conn
    conn.close()
    os.unlink(path)


def test_create_db_creates_all_tables(db):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'players', 'matches', 'xg_events', 'player_ratings'} <= tables


def test_upsert_player(db):
    upsert_player(db, 'p1', 'Harry Kane', 'England')
    db.commit()
    row = db.execute("SELECT name, nationality FROM players WHERE player_id='p1'").fetchone()
    assert row['name'] == 'Harry Kane'
    assert row['nationality'] == 'England'


def test_upsert_player_idempotent(db):
    upsert_player(db, 'p1', 'Harry Kane')
    upsert_player(db, 'p1', 'Harry Kane')
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM players WHERE player_id='p1'").fetchone()[0]
    assert count == 1


def test_insert_match(db):
    insert_match(db, 'm1', '2023-01-15', 'Arsenal', 'Chelsea', '2022-23', 'statsbomb')
    db.commit()
    row = db.execute("SELECT home_team, source FROM matches WHERE match_id='m1'").fetchone()
    assert row['home_team'] == 'Arsenal'
    assert row['source'] == 'statsbomb'


def test_get_current_ratings_returns_latest(db):
    upsert_player(db, 'p1', 'Player One')
    insert_match(db, 'm1', '2023-01-01', 'A', 'B', '2022-23', 'statsbomb')
    insert_match(db, 'm2', '2023-01-15', 'A', 'B', '2022-23', 'statsbomb')
    db.commit()
    upsert_player_rating(db, 'p1', 'm1', '2023-01-01', 1010.0, 10.0, 'A')
    upsert_player_rating(db, 'p1', 'm2', '2023-01-15', 1025.0, 15.0, 'A')
    db.commit()
    ratings = get_current_ratings(db)
    assert ratings['p1'] == 1025.0


def test_get_player_history_ordered_by_date(db):
    upsert_player(db, 'p1', 'Player One')
    insert_match(db, 'm1', '2023-01-01', 'Arsenal', 'Chelsea', '2022-23', 'statsbomb')
    insert_match(db, 'm2', '2023-01-15', 'Arsenal', 'Spurs', '2022-23', 'statsbomb')
    db.commit()
    upsert_player_rating(db, 'p1', 'm1', '2023-01-01', 1010.0, 10.0, 'Arsenal')
    upsert_player_rating(db, 'p1', 'm2', '2023-01-15', 1020.0, 10.0, 'Arsenal')
    db.commit()
    history = get_player_history(db, 'p1')
    assert len(history) == 2
    assert history[0]['rating_after'] == 1010.0
    assert history[1]['rating_after'] == 1020.0
    assert history[0]['player_team'] == 'Arsenal'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.db'`

- [ ] **Step 3: Implement `src/db.py`**

```python
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    player_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    nationality TEXT
);
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    season TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('statsbomb', 'understat'))
);
CREATE TABLE IF NOT EXISTS xg_events (
    event_id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    minute INTEGER NOT NULL,
    xg_value REAL NOT NULL,
    shooting_team TEXT NOT NULL,
    shooter_player_id TEXT REFERENCES players(player_id)
);
CREATE TABLE IF NOT EXISTS player_ratings (
    player_id TEXT NOT NULL REFERENCES players(player_id),
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    date TEXT NOT NULL,
    rating_after REAL NOT NULL,
    rating_delta REAL NOT NULL,
    player_team TEXT NOT NULL,
    PRIMARY KEY (player_id, match_id)
);
"""


def create_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_player(conn: sqlite3.Connection, player_id: str, name: str,
                  nationality: Optional[str] = None) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, name, nationality) VALUES (?, ?, ?)",
        (player_id, name, nationality)
    )


def insert_match(conn: sqlite3.Connection, match_id: str, date: str, home_team: str,
                 away_team: str, season: str, source: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO matches (match_id, date, home_team, away_team, season, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (match_id, date, home_team, away_team, season, source)
    )


def insert_xg_event(conn: sqlite3.Connection, event_id: str, match_id: str, minute: int,
                    xg_value: float, shooting_team: str,
                    shooter_player_id: Optional[str] = None) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO xg_events "
        "(event_id, match_id, minute, xg_value, shooting_team, shooter_player_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, match_id, minute, xg_value, shooting_team, shooter_player_id)
    )


def upsert_player_rating(conn: sqlite3.Connection, player_id: str, match_id: str, date: str,
                         rating_after: float, rating_delta: float, player_team: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO player_ratings "
        "(player_id, match_id, date, rating_after, rating_delta, player_team) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (player_id, match_id, date, rating_after, rating_delta, player_team)
    )


def get_current_ratings(conn: sqlite3.Connection) -> Dict[str, float]:
    rows = conn.execute("""
        SELECT pr.player_id, pr.rating_after
        FROM player_ratings pr
        INNER JOIN (
            SELECT player_id, MAX(date) AS max_date
            FROM player_ratings GROUP BY player_id
        ) latest ON pr.player_id = latest.player_id AND pr.date = latest.max_date
    """).fetchall()
    return {row['player_id']: row['rating_after'] for row in rows}


def get_player_history(conn: sqlite3.Connection, player_id: str) -> List[Dict]:
    rows = conn.execute("""
        SELECT pr.date, pr.rating_after, pr.rating_delta, pr.player_team,
               m.home_team, m.away_team, m.season, m.match_id
        FROM player_ratings pr
        JOIN matches m ON pr.match_id = m.match_id
        WHERE pr.player_id = ?
        ORDER BY pr.date
    """, (player_id,)).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db.py
git commit -m "feat: database schema and CRUD module"
```

---

### Task 3: ELO calculation module

**Files:**
- Create: `src/elo.py`
- Create: `tests/test_elo.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_elo.py`:

```python
from src.elo import BASELINE_RATING, get_players_on_pitch, apply_xg_event, process_match


def test_get_players_on_pitch_no_subs():
    result = get_players_on_pitch(['p1', 'p2', 'p3'], [], minute=45)
    assert set(result) == {'p1', 'p2', 'p3'}


def test_get_players_on_pitch_sub_applied_before_event():
    subs = [{'minute': 60, 'player_off_id': 'p1', 'player_on_id': 'p4', 'team_id': 't1'}]
    result = get_players_on_pitch(['p1', 'p2'], subs, minute=75)
    assert 'p1' not in result
    assert 'p4' in result
    assert 'p2' in result


def test_get_players_on_pitch_sub_not_yet_applied():
    subs = [{'minute': 80, 'player_off_id': 'p1', 'player_on_id': 'p4', 'team_id': 't1'}]
    result = get_players_on_pitch(['p1', 'p2'], subs, minute=70)
    assert 'p1' in result
    assert 'p4' not in result


def test_apply_xg_event_updates_both_teams():
    ratings = {'p1': 1000.0, 'p2': 1000.0}
    updated = apply_xg_event(ratings, attacking_players=['p1'], defending_players=['p2'], xg_value=0.3)
    assert abs(updated['p1'] - 1000.3) < 1e-9
    assert abs(updated['p2'] - 999.7) < 1e-9


def test_apply_xg_event_new_player_starts_at_baseline():
    updated = apply_xg_event({}, attacking_players=['new'], defending_players=[], xg_value=0.5)
    assert abs(updated['new'] - (BASELINE_RATING + 0.5)) < 1e-9


def test_apply_xg_event_does_not_mutate_input():
    ratings = {'p1': 1000.0}
    apply_xg_event(ratings, ['p1'], [], 0.5)
    assert ratings['p1'] == 1000.0


def test_process_match_correct_deltas():
    ratings = {'p1': 1000.0, 'p2': 1000.0, 'p3': 1000.0, 'p4': 1000.0}
    xg_events = [
        {'minute': 30, 'xg': 0.4, 'shooting_team_id': 'home'},
        {'minute': 70, 'xg': 0.2, 'shooting_team_id': 'away'},
    ]
    _, deltas = process_match(
        ratings=ratings,
        home_team_id='home',
        away_team_id='away',
        home_starters=['p1', 'p2'],
        away_starters=['p3', 'p4'],
        substitutions=[],
        xg_events=xg_events
    )
    # p1, p2: +0.4 (home shot) then -0.2 (away shot) = +0.2
    # p3, p4: -0.4 (home shot) then +0.2 (away shot) = -0.2
    assert abs(deltas['p1'] - 0.2) < 1e-9
    assert abs(deltas['p3'] - (-0.2)) < 1e-9


def test_process_match_does_not_mutate_input_ratings():
    ratings = {'p1': 1000.0}
    process_match(ratings, 'home', 'away', ['p1'], [], [], [])
    assert ratings['p1'] == 1000.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_elo.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.elo'`

- [ ] **Step 3: Implement `src/elo.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_elo.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/elo.py tests/test_elo.py
git commit -m "feat: ELO calculation module with lineup tracking"
```

---

### Task 4: StatsBomb data loader

**Files:**
- Create: `src/statsbomb_loader.py`

No unit tests — functions call the StatsBomb API; verified by smoke test in terminal.

- [ ] **Step 1: Create `src/statsbomb_loader.py`**

```python
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
```

- [ ] **Step 2: Smoke test**

```bash
python -c "from src.statsbomb_loader import get_available_seasons; print(get_available_seasons())"
```

Expected: DataFrame with `season_id` and `season_name` columns. Note the season IDs — you'll need them in `01_fetch_data.ipynb`.

- [ ] **Step 3: Commit**

```bash
git add src/statsbomb_loader.py
git commit -m "feat: StatsBomb data loader"
```

---

### Task 5: understat data loader

**Files:**
- Create: `src/understat_loader.py`

- [ ] **Step 1: Create `src/understat_loader.py`**

```python
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
    Pairing is best-effort within ±5 minutes. Minutes are approximate.
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
    Return list of shot dicts with keys: event_id, minute, xg, shooting_team_id, shooter_player_id.
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
            'shooter_player_id': f"us_{shot.get('player_id', '')}"
        })
    return result
```

- [ ] **Step 2: Smoke test**

```bash
python -c "
from src.understat_loader import get_season_results
results = get_season_results(2022)
print(f'Found {len(results)} matches for 2022-23')
print(list(results[0].keys()))
"
```

Expected: `Found 380 matches for 2022-23`, with keys including `id`, `datetime`, `h`, `a`.

- [ ] **Step 3: Commit**

```bash
git add src/understat_loader.py
git commit -m "feat: understat data loader"
```

---

### Task 6: Notebook 01 — fetch and cache raw data

**Files:**
- Create: `notebooks/01_fetch_data.ipynb`

This notebook fetches all available data and writes to `data/raw/` as JSON. It is idempotent — re-running skips already-cached files.

- [ ] **Step 1: Create `notebooks/01_fetch_data.ipynb`**

The notebook must contain these cells in order:

**Cell 1 — setup:**
```python
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path('..').resolve()))
RAW_DIR = Path('../data/raw')
RAW_DIR.mkdir(parents=True, exist_ok=True)
```

**Cell 2 — fetch StatsBomb seasons:**
```python
from src.statsbomb_loader import (
    get_available_seasons, get_matches, get_starters,
    get_substitutions, get_shots, get_player_names
)

seasons = get_available_seasons()
print(seasons)
```

**Cell 3 — fetch StatsBomb matches and events per season:**
```python
for _, season in seasons.iterrows():
    season_id = int(season['season_id'])
    season_name = season['season_name']
    out_file = RAW_DIR / f"sb_matches_{season_id}.json"
    if out_file.exists():
        print(f"[SKIP] {season_name}")
        continue

    print(f"[FETCH] {season_name} ...")
    matches = get_matches(season_id)
    records = []

    for _, match in matches.iterrows():
        mid = int(match['match_id'])
        home = str(match['home_team'])
        away = str(match['away_team'])
        try:
            starters = get_starters(mid)
            subs = get_substitutions(mid, home, away)
            shots = get_shots(mid)
            names = get_player_names(mid)
        except Exception as e:
            print(f"  [ERROR] match {mid}: {e}")
            continue

        records.append({
            'match_id': f"sb_{mid}",
            'date': str(match['match_date']),
            'home_team': home,
            'away_team': away,
            'home_team_id': home,
            'away_team_id': away,
            'season': season_name,
            'source': 'statsbomb',
            'starters': starters,
            'substitutions': subs,
            'shots': shots,
            'player_names': names
        })

    with open(out_file, 'w') as f:
        json.dump(records, f)
    print(f"  Saved {len(records)} matches to {out_file.name}")
```

**Cell 4 — fetch understat seasons:**
```python
from src.understat_loader import (
    get_season_results, get_match_shots, get_match_roster,
    parse_starters, parse_substitutions, parse_shots
)

# 5 seasons back from 2025-26: starting years 2020, 2021, 2022, 2023, 2024
UNDERSTAT_YEARS = [2020, 2021, 2022, 2023, 2024]

for year in UNDERSTAT_YEARS:
    season_label = f"{year}-{str(year + 1)[-2:]}"
    out_file = RAW_DIR / f"us_matches_{year}.json"
    if out_file.exists():
        print(f"[SKIP] {season_label}")
        continue

    print(f"[FETCH] {season_label} ...")
    results = get_season_results(year)
    records = []

    for match in results:
        mid = int(match['id'])
        home_team = match['h']['title']
        away_team = match['a']['title']
        home_id = f"us_team_{match['h']['id']}"
        away_id = f"us_team_{match['a']['id']}"
        date_str = match['datetime'][:10]

        try:
            shots_raw = get_match_shots(mid)
            roster_raw = get_match_roster(mid)
        except Exception as e:
            print(f"  [ERROR] match {mid}: {e}")
            continue

        home_starters = parse_starters(roster_raw, 'h')
        away_starters = parse_starters(roster_raw, 'a')
        home_subs = parse_substitutions(roster_raw, 'h', home_id)
        away_subs = parse_substitutions(roster_raw, 'a', away_id)
        home_shots = parse_shots(shots_raw, 'h', home_id, mid)
        away_shots = parse_shots(shots_raw, 'a', away_id, mid)

        player_names = {
            f"us_{p['id']}": p['player']
            for p in roster_raw.get('h', []) + roster_raw.get('a', [])
        }

        records.append({
            'match_id': f"us_{mid}",
            'date': date_str,
            'home_team': home_team,
            'away_team': away_team,
            'home_team_id': home_id,
            'away_team_id': away_id,
            'season': season_label,
            'source': 'understat',
            'starters': {home_team: home_starters, away_team: away_starters},
            'substitutions': home_subs + away_subs,
            'shots': home_shots + away_shots,
            'player_names': player_names
        })

    with open(out_file, 'w') as f:
        json.dump(records, f)
    print(f"  Saved {len(records)} matches to {out_file.name}")

print("Done!")
```

- [ ] **Step 2: Run the notebook**

Open Jupyter: `jupyter notebook notebooks/01_fetch_data.ipynb`

Run all cells. The understat cells fetch ~380 matches × 5 seasons with 2 API calls each — expect **30–60 minutes** total. The cell prints `[SKIP]` for any file already cached, so it's safe to re-run after interruptions.

Expected: `data/raw/` contains `sb_matches_*.json` and `us_matches_*.json` files.

- [ ] **Step 3: Commit**

```bash
git add notebooks/01_fetch_data.ipynb data/raw/.gitkeep
git commit -m "feat: notebook 01 - data fetching pipeline"
```

(Raw JSON files are gitignored; only the notebook is committed.)

---

### Task 7: Notebook 02 — calculate ELO

**Files:**
- Create: `notebooks/02_calculate_elo.ipynb`

- [ ] **Step 1: Create `notebooks/02_calculate_elo.ipynb`**

**Cell 1 — setup:**
```python
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path('..').resolve()))
RAW_DIR = Path('../data/raw')
DB_PATH = str(Path('../data/elo.db'))
```

**Cell 2 — initialize DB:**
```python
from src.db import create_db

conn = create_db(DB_PATH)
print(f"DB initialized at {DB_PATH}")
```

**Cell 3 — load and sort all raw match records by date:**
```python
all_matches = []
for f in sorted(RAW_DIR.glob('*.json')):
    with open(f) as fh:
        all_matches.extend(json.load(fh))

all_matches.sort(key=lambda m: m['date'])
print(f"Loaded {len(all_matches)} matches")
print(f"Date range: {all_matches[0]['date']} — {all_matches[-1]['date']}")
```

**Cell 4 — run ELO pipeline:**
```python
from src.db import (
    upsert_player, insert_match, insert_xg_event,
    upsert_player_rating, get_current_ratings
)
from src.elo import process_match, BASELINE_RATING

ratings = get_current_ratings(conn)
already_processed = {
    row[0] for row in conn.execute("SELECT match_id FROM matches").fetchall()
}

skipped = 0
for match in all_matches:
    match_id = match['match_id']
    if match_id in already_processed:
        skipped += 1
        continue

    home_team = match['home_team']
    away_team = match['away_team']
    home_team_id = match['home_team_id']
    away_team_id = match['away_team_id']

    starters = match['starters']
    home_starters = starters.get(home_team, [])
    away_starters = starters.get(away_team, [])
    subs = match['substitutions']

    insert_match(conn, match_id, match['date'], home_team, away_team,
                 match['season'], match['source'])
    for pid, name in match['player_names'].items():
        upsert_player(conn, pid, name)
    for shot in match['shots']:
        insert_xg_event(
            conn, shot['event_id'], match_id, shot['minute'],
            shot['xg'], shot['shooting_team_id'],
            shot.get('shooter_player_id')
        )

    updated_ratings, deltas = process_match(
        ratings=ratings,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_starters=home_starters,
        away_starters=away_starters,
        substitutions=subs,
        xg_events=match['shots']
    )

    all_pids = set(home_starters + away_starters + [s['player_on_id'] for s in subs])
    for pid in all_pids:
        team = home_team if pid in home_starters or any(
            s['player_on_id'] == pid and s['team_id'] == home_team_id for s in subs
        ) else away_team
        upsert_player_rating(
            conn, pid, match_id, match['date'],
            updated_ratings.get(pid, BASELINE_RATING),
            deltas.get(pid, 0.0),
            team
        )

    ratings = updated_ratings

conn.commit()
print(f"Processed {len(all_matches) - skipped} new matches, skipped {skipped}.")
```

**Cell 5 — sanity check top 10:**
```python
top = conn.execute("""
    SELECT p.name, pr.rating_after
    FROM player_ratings pr
    JOIN players p ON pr.player_id = p.player_id
    INNER JOIN (
        SELECT player_id, MAX(date) AS d FROM player_ratings GROUP BY player_id
    ) latest ON pr.player_id = latest.player_id AND pr.date = latest.d
    ORDER BY pr.rating_after DESC LIMIT 10
""").fetchall()

print("Top 10 by current ELO:")
for row in top:
    print(f"  {row[0]}: {row[1]:.1f}")
```

- [ ] **Step 2: Run the notebook**

Open Jupyter: `jupyter notebook notebooks/02_calculate_elo.ipynb`

Run all cells. Expected: Cell 5 prints 10 player names with ratings.

- [ ] **Step 3: Commit**

```bash
git add notebooks/02_calculate_elo.ipynb data/elo.db
git commit -m "feat: notebook 02 - ELO pipeline; add data/elo.db"
```

---

### Task 8: Site builder module

**Files:**
- Create: `src/site_builder.py`
- Create: `tests/test_site_builder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_site_builder.py`:

```python
from src.site_builder import build_sparkline_svg, build_leaderboard_html, build_site


def test_sparkline_returns_svg_element():
    svg = build_sparkline_svg([1000, 1005, 1003, 1010, 1008])
    assert svg.startswith('<svg')
    assert '</svg>' in svg


def test_sparkline_single_value_does_not_crash():
    svg = build_sparkline_svg([1000])
    assert '<svg' in svg


def test_leaderboard_contains_player_name():
    players = [{
        'player_id': 'p1', 'name': 'Harry Kane', 'current_rating': 1050.5,
        'rating_delta_30d': 12.3, 'matches_played': 80,
        'recent_ratings': [1000, 1010, 1020, 1030, 1050]
    }]
    html = build_leaderboard_html(players)
    assert 'Harry Kane' in html
    assert '1050' in html


def test_leaderboard_contains_all_players():
    players = [
        {'player_id': 'p1', 'name': 'Player A', 'current_rating': 1100.0,
         'rating_delta_30d': 5.0, 'matches_played': 50, 'recent_ratings': [1090, 1100]},
        {'player_id': 'p2', 'name': 'Player B', 'current_rating': 900.0,
         'rating_delta_30d': -3.0, 'matches_played': 30, 'recent_ratings': [910, 900]},
    ]
    html = build_leaderboard_html(players)
    assert 'Player A' in html
    assert 'Player B' in html


def test_build_site_includes_plotly_cdn():
    html = build_site([], {})
    assert 'plotly' in html.lower()


def test_build_site_embeds_player_history_json():
    history = {'p1': [{'date': '2023-01-01', 'rating_after': 1010.0, 'rating_delta': 10.0,
                        'player_team': 'Arsenal', 'home_team': 'Arsenal',
                        'away_team': 'Chelsea', 'season': '2022-23'}]}
    html = build_site([], history)
    assert '2023-01-01' in html
    assert '1010' in html
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_site_builder.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.site_builder'`

- [ ] **Step 3: Implement `src/site_builder.py`**

```python
import json
from typing import Dict, List


def build_sparkline_svg(ratings: List[float], width: int = 80, height: int = 20) -> str:
    if len(ratings) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    lo, hi = min(ratings), max(ratings)
    span = hi - lo if hi != lo else 1.0
    pts = []
    for i, r in enumerate(ratings):
        x = i * width / (len(ratings) - 1)
        y = height - (r - lo) / span * height
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#22c55e" if ratings[-1] >= ratings[0] else "#ef4444"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'</svg>'
    )


def build_leaderboard_html(players: List[Dict]) -> str:
    rows = []
    for i, p in enumerate(players, 1):
        d = p['rating_delta_30d']
        d_color = "#22c55e" if d >= 0 else "#ef4444"
        d_str = f"+{d:.1f}" if d >= 0 else f"{d:.1f}"
        rows.append(
            f'<tr class="player-row" data-player-id="{p["player_id"]}" style="cursor:pointer">'
            f'<td>{i}</td>'
            f'<td><strong>{p["name"]}</strong></td>'
            f'<td>{p["current_rating"]:.1f}</td>'
            f'<td style="color:{d_color}">{d_str}</td>'
            f'<td>{p["matches_played"]}</td>'
            f'<td>{build_sparkline_svg(p["recent_ratings"])}</td>'
            f'</tr>'
        )
    return (
        '<table id="leaderboard">'
        '<thead><tr><th>#</th><th>Player</th><th>ELO</th>'
        '<th>30d Δ</th><th>Matches</th><th>Trend</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
    )


def build_site(players: List[Dict], player_histories: Dict[str, List[Dict]]) -> str:
    leaderboard = build_leaderboard_html(players)
    histories_json = json.dumps(player_histories)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Premier League Player ELO</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 1100px; margin: 0 auto; padding: 1rem 2rem; background: #0f0f0f; color: #e5e5e5; }}
  h1 {{ color: #38bdf8; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #94a3b8; margin-top: 0; font-size: 0.9rem; }}
  .filter-bar {{ display: flex; gap: 1rem; margin-bottom: 1rem; align-items: center; flex-wrap: wrap; }}
  .filter-bar label {{ color: #94a3b8; font-size: 0.85rem; }}
  .filter-bar input {{ background: #1a1a1a; border: 1px solid #333; color: #e5e5e5; padding: 0.3rem 0.6rem; border-radius: 4px; }}
  #leaderboard {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
  #leaderboard th {{ text-align: left; padding: 0.5rem 1rem; border-bottom: 2px solid #333; color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  #leaderboard td {{ padding: 0.5rem 1rem; border-bottom: 1px solid #1f1f1f; font-size: 0.9rem; }}
  #leaderboard tr:hover td {{ background: #1a1a1a; }}
  #leaderboard tr.selected td {{ background: #1e3a5f; }}
  #detail {{ background: #141414; border: 1px solid #2a2a2a; border-radius: 8px; padding: 1.25rem; margin-top: 1rem; display: none; }}
  #detail h2 {{ color: #38bdf8; margin-top: 0; }}
</style>
</head>
<body>
<h1>Premier League Player ELO</h1>
<p class="subtitle">Player ratings calculated from xG events: +xG for attackers on the pitch, −xG for defenders. Click a player to see their full timeline. Data: StatsBomb + understat, 2020–2025.</p>

<div class="filter-bar">
  <label>Min matches: <input type="number" id="min-matches" value="10" min="1" style="width:60px"></label>
  <label>Search: <input type="text" id="search" placeholder="Player name…"></label>
</div>

{leaderboard}

<div id="detail">
  <h2 id="detail-name"></h2>
  <div id="detail-chart"></div>
</div>

<script>
const HISTORIES = {histories_json};

document.getElementById('min-matches').addEventListener('input', filterTable);
document.getElementById('search').addEventListener('input', filterTable);

function filterTable() {{
  const min = parseInt(document.getElementById('min-matches').value) || 0;
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('#leaderboard tbody tr').forEach(row => {{
    const matches = parseInt(row.cells[4].textContent);
    const name = row.cells[1].textContent.toLowerCase();
    row.style.display = (matches >= min && name.includes(q)) ? '' : 'none';
  }});
}}

document.querySelectorAll('.player-row').forEach(row => {{
  row.addEventListener('click', () => {{
    document.querySelectorAll('.player-row').forEach(r => r.classList.remove('selected'));
    row.classList.add('selected');
    showDetail(row.dataset.playerId, row.cells[1].textContent.trim());
  }});
}});

function showDetail(pid, name) {{
  const history = HISTORIES[pid];
  if (!history || history.length === 0) return;

  const dates = history.map(h => h.date);
  const ratings = history.map(h => h.rating_after);
  const tips = history.map(h =>
    h.home_team + ' vs ' + h.away_team +
    '<br>' + (h.rating_delta >= 0 ? '+' : '') + h.rating_delta.toFixed(2) + ' ELO'
  );

  // Detect transfers: when player_team changes between consecutive matches
  const shapes = [], annotations = [];
  for (let i = 1; i < history.length; i++) {{
    if (history[i].player_team !== history[i - 1].player_team) {{
      shapes.push({{
        type: 'line', x0: dates[i], x1: dates[i],
        y0: 0, y1: 1, yref: 'paper',
        line: {{ color: '#f59e0b', width: 1, dash: 'dot' }}
      }});
      annotations.push({{
        x: dates[i], y: 1.08, yref: 'paper',
        text: history[i].player_team, showarrow: false,
        font: {{ color: '#f59e0b', size: 9 }}
      }});
    }}
  }}

  Plotly.newPlot('detail-chart', [{{
    x: dates, y: ratings, mode: 'lines+markers',
    marker: {{ size: 4, color: '#38bdf8' }},
    line: {{ color: '#38bdf8', width: 2 }},
    text: tips,
    hovertemplate: '%{{text}}<br>ELO: %{{y:.1f}}<extra></extra>'
  }}], {{
    paper_bgcolor: '#141414', plot_bgcolor: '#141414',
    font: {{ color: '#e5e5e5' }},
    xaxis: {{ gridcolor: '#2a2a2a', title: 'Date' }},
    yaxis: {{ gridcolor: '#2a2a2a', title: 'ELO Rating' }},
    shapes, annotations,
    margin: {{ t: 30, r: 20, b: 50, l: 60 }}, height: 320
  }}, {{responsive: true}});

  document.getElementById('detail-name').textContent = name;
  document.getElementById('detail').style.display = 'block';
  document.getElementById('detail').scrollIntoView({{behavior: 'smooth'}});
}}
</script>
</body>
</html>"""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_site_builder.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/site_builder.py tests/test_site_builder.py
git commit -m "feat: site builder — leaderboard, sparklines, player detail with transfer markers"
```

---

### Task 9: Notebook 03 — build site

**Files:**
- Create: `notebooks/03_build_site.ipynb`

- [ ] **Step 1: Create `notebooks/03_build_site.ipynb`**

**Cell 1 — setup:**
```python
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path('..').resolve()))
DB_PATH = str(Path('../data/elo.db'))
SITE_PATH = Path('../index.html')
```

**Cell 2 — open DB:**
```python
from src.db import create_db, get_player_history
conn = create_db(DB_PATH)
print("DB opened.")
```

**Cell 3 — build leaderboard data:**
```python
cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

rows = conn.execute("""
    SELECT p.player_id, p.name, pr.rating_after AS current_rating,
           COUNT(DISTINCT pr_all.match_id) AS matches_played
    FROM players p
    JOIN player_ratings pr ON p.player_id = pr.player_id
    JOIN (SELECT player_id, MAX(date) AS d FROM player_ratings GROUP BY player_id) l
      ON pr.player_id = l.player_id AND pr.date = l.d
    JOIN player_ratings pr_all ON p.player_id = pr_all.player_id
    GROUP BY p.player_id
    ORDER BY pr.rating_after DESC
""").fetchall()

players = []
for row in rows:
    pid, name, cur, matches = row[0], row[1], row[2], row[3]

    old = conn.execute("""
        SELECT rating_after FROM player_ratings
        WHERE player_id = ? AND date <= ?
        ORDER BY date DESC LIMIT 1
    """, (pid, cutoff)).fetchone()
    delta_30d = cur - (old[0] if old else cur)

    recent = conn.execute("""
        SELECT rating_after FROM player_ratings
        WHERE player_id = ? ORDER BY date DESC LIMIT 20
    """, (pid,)).fetchall()
    recent_ratings = [r[0] for r in reversed(recent)]

    players.append({
        'player_id': pid, 'name': name, 'current_rating': cur,
        'rating_delta_30d': delta_30d, 'matches_played': matches,
        'recent_ratings': recent_ratings
    })

print(f"Loaded {len(players)} players. Top 5:")
for p in players[:5]:
    print(f"  {p['name']}: {p['current_rating']:.1f} ({p['rating_delta_30d']:+.1f} 30d)")
```

**Cell 4 — build player histories:**
```python
player_histories = {p['player_id']: get_player_history(conn, p['player_id']) for p in players}
print(f"Built histories for {len(player_histories)} players.")
```

**Cell 5 — generate index.html:**
```python
from src.site_builder import build_site

html = build_site(players, player_histories)
SITE_PATH.write_text(html, encoding='utf-8')
size_mb = SITE_PATH.stat().st_size / 1_000_000
print(f"Written {size_mb:.1f} MB to {SITE_PATH.resolve()}")
print(f"Open in browser: file:///{SITE_PATH.resolve()}")
```

- [ ] **Step 2: Run the notebook**

Open Jupyter: `jupyter notebook notebooks/03_build_site.ipynb`

Run all cells. Expected: `index.html` written to the project root.

- [ ] **Step 3: Open locally and verify**

Open the printed file path in your browser. Confirm:
- Leaderboard table renders with player names and ratings
- Clicking a player opens the ELO timeline below the table
- Vertical dotted lines appear where a player changed clubs
- Min-matches filter and name search both work

- [ ] **Step 4: Commit and push**

```bash
git add notebooks/03_build_site.ipynb index.html
git commit -m "feat: notebook 03 - site generation; add index.html"
git push origin main
```

---

### Task 10: README and GitHub Pages

**Files:**
- Create: `README.md`

- [ ] **Step 1: Run all tests one final time**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Create `README.md`**

```markdown
# Premier League Player ELO

Player-level ELO ratings for Premier League footballers, calculated from xG shot events across 5 seasons (2020–2025).

**Live site:** https://noskirec.github.io/premier-league-elo/

## Methodology

For every shot in every match, all 11 players on the **attacking team** receive `+xG` added to their rating, and all 11 players on the **defending team** receive `−xG` subtracted. Ratings accumulate continuously — a player's rating carries across club transfers.

**Baseline rating:** 1000 for all players.

This rewards players who are on the pitch for high-quality attacking chances and penalizes those on the pitch when their side concedes them.

**Future enhancement:** ELO-style probabilistic updates where the magnitude of rating change depends on how surprising the shot outcome was relative to xG expectation.

## Data Sources

| Source | Library | Coverage |
|---|---|---|
| [StatsBomb open data](https://github.com/statsbomb/open-data) | `statsbombpy` | ~3 PL seasons, full event data |
| [understat.com](https://understat.com) | `understat` | All PL seasons from 2020, xG + lineup |

Understat substitution timing is approximate (±5 minutes).

## Running the Pipeline

```bash
pip install -r requirements.txt
```

Run notebooks in order:

1. `notebooks/01_fetch_data.ipynb` — fetches and caches raw data (~30–60 min)
2. `notebooks/02_calculate_elo.ipynb` — calculates ELO and writes `data/elo.db`
3. `notebooks/03_build_site.ipynb` — generates `index.html`

Re-running notebooks is safe — fetching skips cached files and ELO skips processed matches.

## Database

`data/elo.db` is a SQLite file you can query directly:

```sql
-- Top 10 players by current ELO
SELECT p.name, pr.rating_after
FROM player_ratings pr
JOIN players p ON pr.player_id = p.player_id
INNER JOIN (SELECT player_id, MAX(date) d FROM player_ratings GROUP BY player_id) l
  ON pr.player_id = l.player_id AND pr.date = l.d
ORDER BY pr.rating_after DESC LIMIT 10;
```

## Tests

```bash
pytest tests/ -v
```
```

- [ ] **Step 3: Commit and push**

```bash
git add README.md
git commit -m "docs: README with methodology, setup, and query examples"
git push origin main
```

- [ ] **Step 4: Enable GitHub Pages**

In the GitHub repo at https://github.com/noskirec/premier-league-elo:
1. Settings → Pages
2. Source: **Deploy from a branch**
3. Branch: `main`, folder: `/ (root)`
4. Click **Save**

Your site will be live at `https://noskirec.github.io/premier-league-elo/` within a few minutes.

---

## Known Limitations & Future Enhancements

- **GitHub Actions automation:** Workflow to re-run the pipeline weekly and auto-commit refreshed data
- **ELO probabilistic model:** Replace simple xG delta with win-probability formula (surprises score bigger)
- **Position weighting:** Discount xG delta for goalkeepers differently than outfield players
- **Exact sub timing for understat:** Use a secondary source for precise substitution minutes
