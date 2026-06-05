# fbref Lineup Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace understat as the source of lineup and substitution data with fbref (via `soccerdata`), while keeping understat for per-shot xG data.

**Architecture:** New `src/fbref_loader.py` pre-fetches an entire season's lineup data from fbref in one `soccerdata.FBref` session (results cached to disk), keyed by normalized `{date}|{home}|{away}` for O(1) per-match lookup. The notebook's understat cell is restructured: shots still come from understat, lineups come from fbref, with a fallback to understat's approximate subs when fbref has no match. `shooter_player_id` is dropped from shot records since fbref and understat player IDs are in different namespaces and the field is not used in ELO calculation.

**Tech Stack:** soccerdata>=0.3, existing Python 3.8.8 Anaconda environment, pytest

---

## File Map

| File | Change |
|---|---|
| `requirements.txt` | Add `soccerdata>=0.3` |
| `src/fbref_loader.py` | **New** — `normalize_team_name` + `get_season_lineups` |
| `src/understat_loader.py` | Remove `shooter_player_id` from `parse_shots` return dicts |
| `tests/test_fbref_loader.py` | **New** — unit tests for `normalize_team_name` |
| `tests/test_understat_loader.py` | **New** — test `parse_shots` no longer includes `shooter_player_id` |
| `notebooks/01_fetch_data.ipynb` | Restructure understat cell to use fbref lineups |

`src/db.py`, `src/elo.py`, `src/site_builder.py`, `src/statsbomb_loader.py`, notebooks 02 and 03, all other tests — **unchanged**.

---

### Task 1: Install soccerdata and update requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add soccerdata to requirements.txt**

Open `C:\Users\Owner\Documents\premier-league-elo\requirements.txt` and add one line after `plotly>=5.18.0`:

```
soccerdata>=0.3
```

Full file should read:
```
statsbombpy>=1.0.3
understat>=0.2.1
aiohttp>=3.9.0
nest-asyncio>=1.6.0
pandas>=2.0.0
plotly>=5.18.0
soccerdata>=0.3
pytest>=7.4.0
jupyter>=1.0.0
ipykernel>=6.0.0
```

- [ ] **Step 2: Install soccerdata**

```powershell
$env:PATH = "C:\Users\Owner\anaconda3\Library\bin;" + $env:PATH
& "C:\Users\Owner\anaconda3\python.exe" -m pip install "soccerdata>=0.3"
```

Expected: `Successfully installed soccerdata-...` (or `Requirement already satisfied`).

- [ ] **Step 3: Smoke-test the install and discover the DataFrame structure**

Run this script from `C:\Users\Owner\Documents\premier-league-elo`:

```powershell
$env:PATH = "C:\Users\Owner\anaconda3\Library\bin;" + $env:PATH
& "C:\Users\Owner\anaconda3\python.exe" -c "
import soccerdata as sd
fbref = sd.FBref(leagues='ENG-Premier League', seasons=2022)
sched = fbref.read_schedule().reset_index()
print('=== SCHEDULE ===')
print('columns:', sched.columns.tolist())
print('index names:', sched.index.names)
print(sched.head(2).to_string())

lineups = fbref.read_lineup().reset_index()
print('\n=== LINEUPS ===')
print('columns:', lineups.columns.tolist())
print('index names:', lineups.index.names)
print(lineups.head(4).to_string())
"
```

Expected output includes two DataFrame structures. **Note the exact column names** — specifically:
- In schedule: the game/match ID column (likely `game`), `date`, `home_team`, `away_team`
- In lineups: the game ID column, team column, player ID column (`player_id`), player name column (`player`), starter indicator, minutes column

The implementation in Task 2 uses `game`, `date`, `home_team`, `away_team`, `team`, `player`, `player_id`, `started`, `minutes` as the expected column names. If any differ in the output above, note the actual names — they are referenced in the Task 2 implementation constants at the top of `fbref_loader.py`.

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/Owner/Documents/premier-league-elo"
git add requirements.txt
git commit -m "feat: add soccerdata dependency"
```

---

### Task 2: `src/fbref_loader.py` with TDD

**Files:**
- Create: `tests/test_fbref_loader.py`
- Create: `src/fbref_loader.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_fbref_loader.py`:

```python
from src.fbref_loader import normalize_team_name


def test_normalize_lowercases():
    assert normalize_team_name("Arsenal") == "arsenal"


def test_normalize_strips_trailing_fc():
    assert normalize_team_name("Fulham FC") == "fulham"


def test_normalize_strips_afc():
    assert normalize_team_name("AFC Bournemouth") == "bournemouth"


def test_normalize_wolves_alias():
    assert normalize_team_name("Wolverhampton Wanderers") == "wolves"


def test_normalize_brighton_alias():
    assert normalize_team_name("Brighton & Hove Albion") == "brighton"


def test_normalize_tottenham_alias():
    assert normalize_team_name("Tottenham Hotspur") == "tottenham"


def test_normalize_west_ham_alias():
    assert normalize_team_name("West Ham United") == "west ham"


def test_normalize_newcastle_alias():
    assert normalize_team_name("Newcastle United") == "newcastle"


def test_normalize_man_utd_alias():
    assert normalize_team_name("Manchester United") == "manchester utd"


def test_normalize_nottingham_alias():
    assert normalize_team_name("Nottingham Forest") == "nott'm forest"


def test_normalize_sheffield_alias():
    assert normalize_team_name("Sheffield United") == "sheffield utd"


def test_normalize_already_short():
    assert normalize_team_name("Chelsea") == "chelsea"


def test_normalize_idempotent():
    # Applying twice gives same result
    name = "Wolverhampton Wanderers"
    assert normalize_team_name(normalize_team_name(name)) == normalize_team_name(name)
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
$env:PATH = "C:\Users\Owner\anaconda3\Library\bin;" + $env:PATH
cd "C:\Users\Owner\Documents\premier-league-elo"
& "C:\Users\Owner\anaconda3\python.exe" -m pytest tests/test_fbref_loader.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.fbref_loader'`

- [ ] **Step 3: Implement `src/fbref_loader.py`**

```python
import soccerdata as sd
from typing import Dict, List

# Column name constants — update these if Task 1 discovery showed different names
_COL_GAME = 'game'
_COL_DATE = 'date'
_COL_HOME = 'home_team'
_COL_AWAY = 'away_team'
_COL_TEAM = 'team'
_COL_PLAYER = 'player'
_COL_PLAYER_ID = 'player_id'
_COL_STARTED = 'started'   # 1/True = starter, 0/False = bench
_COL_MINUTES = 'minutes'

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
    """Normalize a team name for cross-source matching (fbref ↔ understat)."""
    s = name.lower().strip()
    # Strip common suffixes
    for suffix in (' fc', ' afc', ' f.c.'):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    # Strip leading AFC
    if s.startswith('afc '):
        s = s[4:]
    return _ALIASES.get(s, s)


def get_season_lineups(season_year: int) -> Dict[str, Dict]:
    """
    Pre-fetch all lineup data for one EPL season from fbref via soccerdata.
    soccerdata caches results to disk — subsequent calls are instant.

    Returns dict keyed by "{date}|{normalize(home)}|{normalize(away)}".
    Each value: {home_starters, away_starters, substitutions, player_names}
    where player IDs are prefixed 'fb_'.

    season_year: calendar start year, e.g. 2022 for 2022-23.
    """
    fbref = sd.FBref(leagues="ENG-Premier League", seasons=season_year)
    sched = fbref.read_schedule().reset_index()
    lineup_df = fbref.read_lineup().reset_index()

    result = {}

    for _, game_row in sched.iterrows():
        game_id = game_row[_COL_GAME]
        date = str(game_row[_COL_DATE])[:10]
        home = str(game_row[_COL_HOME])
        away = str(game_row[_COL_AWAY])
        key = f"{date}|{normalize_team_name(home)}|{normalize_team_name(away)}"

        gdf = lineup_df[lineup_df[_COL_GAME] == game_id]
        if gdf.empty:
            continue

        home_starters, away_starters, substitutions, player_names = [], [], [], {}

        for team_name, is_home in [(home, True), (away, False)]:
            tdf = gdf[gdf[_COL_TEAM] == team_name]
            if tdf.empty:
                continue

            # Populate player names for all squad members
            for _, row in tdf.iterrows():
                pid = f"fb_{row[_COL_PLAYER_ID]}"
                player_names[pid] = str(row[_COL_PLAYER])

            # Separate starters from bench
            if _COL_STARTED in tdf.columns:
                starters_df = tdf[tdf[_COL_STARTED].astype(bool)]
                bench_df = tdf[~tdf[_COL_STARTED].astype(bool)]
            else:
                # Fallback: sort by minutes desc, top 11 are starters
                tdf_sorted = tdf.sort_values(_COL_MINUTES, ascending=False)
                starters_df = tdf_sorted.head(11)
                bench_df = tdf_sorted.iloc[11:]

            starter_ids = [f"fb_{r[_COL_PLAYER_ID]}" for _, r in starters_df.iterrows()]
            if is_home:
                home_starters = starter_ids
            else:
                away_starters = starter_ids

            # Build substitutions: starters who didn't play full game
            used_bench = set()
            for _, s_row in starters_df.iterrows():
                mins = int(s_row.get(_COL_MINUTES, 90) or 90)
                if mins >= 89:
                    continue  # played full game, no substitution
                # Find the bench player who came on closest to this minute
                for _, b_row in bench_df.iterrows():
                    if b_row[_COL_PLAYER_ID] in used_bench:
                        continue
                    b_mins = int(b_row.get(_COL_MINUTES, 0) or 0)
                    # fbref minutes for a sub = minutes played, so came_on ≈ 90 - b_mins
                    came_on = 90 - b_mins
                    if abs(came_on - mins) <= 5:
                        substitutions.append({
                            'minute': mins,
                            'player_off_id': f"fb_{s_row[_COL_PLAYER_ID]}",
                            'player_on_id': f"fb_{b_row[_COL_PLAYER_ID]}",
                            'team_id': team_name,
                        })
                        used_bench.add(b_row[_COL_PLAYER_ID])
                        break

        result[key] = {
            'home_starters': home_starters,
            'away_starters': away_starters,
            'substitutions': substitutions,
            'player_names': player_names,
        }

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
$env:PATH = "C:\Users\Owner\anaconda3\Library\bin;" + $env:PATH
cd "C:\Users\Owner\Documents\premier-league-elo"
& "C:\Users\Owner\anaconda3\python.exe" -m pytest tests/test_fbref_loader.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Smoke-test `get_season_lineups` against real fbref data**

```powershell
$env:PATH = "C:\Users\Owner\anaconda3\Library\bin;" + $env:PATH
cd "C:\Users\Owner\Documents\premier-league-elo"
& "C:\Users\Owner\anaconda3\python.exe" -c "
import sys; sys.path.insert(0, '.')
from src.fbref_loader import get_season_lineups
lineups = get_season_lineups(2022)
print(f'Fetched {len(lineups)} matches')
sample_key = next(iter(lineups))
sample = lineups[sample_key]
print('Sample key:', sample_key)
print('home_starters count:', len(sample['home_starters']))
print('away_starters count:', len(sample['away_starters']))
print('substitutions count:', len(sample['substitutions']))
print('player_names count:', len(sample['player_names']))
if sample['substitutions']:
    print('First sub:', sample['substitutions'][0])
"
```

Expected:
- `Fetched 380 matches` (or close — some may not have lineup data yet)
- `home_starters count: 11`
- `away_starters count: 11`
- `substitutions count:` between 2 and 9 (typical for a PL match)
- First sub shows exact `minute`, `player_off_id` with `fb_` prefix, `player_on_id` with `fb_` prefix

If the counts are 0 for starters, the `_COL_STARTED` or column name constants need adjusting — print `sample` in full and compare against the Task 1 discovery output.

- [ ] **Step 6: Commit**

```bash
git add src/fbref_loader.py tests/test_fbref_loader.py requirements.txt
git commit -m "feat: fbref lineup loader with season-level pre-fetch"
```

---

### Task 3: Remove `shooter_player_id` from `understat_loader.parse_shots`

**Files:**
- Modify: `src/understat_loader.py:98-114`
- Create: `tests/test_understat_loader.py`

Without this change, `insert_xg_event` receives `us_` prefixed player IDs that don't exist in the `players` table (which now only has `fb_` IDs), causing a foreign-key violation.

- [ ] **Step 1: Write failing test**

Create `tests/test_understat_loader.py`:

```python
from src.understat_loader import parse_shots


def test_parse_shots_excludes_shooter_player_id():
    shots = {
        'h': [
            {'xG': '0.35', 'minute': '23', 'player_id': '999', 'player': 'Test Player'},
        ]
    }
    result = parse_shots(shots, 'h', 'us_team_1', match_id=42)
    assert len(result) == 1
    assert 'shooter_player_id' not in result[0]


def test_parse_shots_filters_zero_xg():
    shots = {
        'h': [
            {'xG': '0.0', 'minute': '10', 'player_id': '1'},
            {'xG': '0.25', 'minute': '55', 'player_id': '2'},
        ]
    }
    result = parse_shots(shots, 'h', 'us_team_1', match_id=1)
    assert len(result) == 1
    assert result[0]['xg'] == 0.25


def test_parse_shots_required_keys():
    shots = {'a': [{'xG': '0.4', 'minute': '70', 'player_id': '5'}]}
    result = parse_shots(shots, 'a', 'us_team_2', match_id=7)
    assert result[0].keys() == {'event_id', 'minute', 'xg', 'shooting_team_id'}
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
$env:PATH = "C:\Users\Owner\anaconda3\Library\bin;" + $env:PATH
cd "C:\Users\Owner\Documents\premier-league-elo"
& "C:\Users\Owner\anaconda3\python.exe" -m pytest tests/test_understat_loader.py -v
```

Expected: `test_parse_shots_excludes_shooter_player_id` FAILS and `test_parse_shots_required_keys` FAILS (current code includes `shooter_player_id`).

- [ ] **Step 3: Update `parse_shots` in `src/understat_loader.py`**

Replace lines 98–114 (the `parse_shots` function) with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
$env:PATH = "C:\Users\Owner\anaconda3\Library\bin;" + $env:PATH
cd "C:\Users\Owner\Documents\premier-league-elo"
& "C:\Users\Owner\anaconda3\python.exe" -m pytest tests/test_understat_loader.py tests/test_fbref_loader.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run full suite to confirm no regressions**

```powershell
$env:PATH = "C:\Users\Owner\anaconda3\Library\bin;" + $env:PATH
cd "C:\Users\Owner\Documents\premier-league-elo"
& "C:\Users\Owner\anaconda3\python.exe" -m pytest tests/ -v
```

Expected: all tests PASS (the existing `test_db.py`, `test_elo.py`, `test_site_builder.py` are unaffected).

- [ ] **Step 6: Commit**

```bash
git add src/understat_loader.py tests/test_understat_loader.py
git commit -m "fix: remove shooter_player_id from parse_shots to avoid cross-source FK violations"
```

---

### Task 4: Update `notebooks/01_fetch_data.ipynb`

**Files:**
- Modify: `notebooks/01_fetch_data.ipynb`

Replace the entire notebook (cells 0–4) with the updated version below. The StatsBomb cells are unchanged. The understat cell is restructured to pre-fetch fbref lineups and use them in the per-match loop.

**Note:** Delete existing `data/raw/us_matches_*.json` cache files before running — they contain stale `us_team_X` IDs and understat player IDs that are incompatible with the new format.

```powershell
Remove-Item "C:\Users\Owner\Documents\premier-league-elo\data\raw\us_matches_*.json" -ErrorAction SilentlyContinue
```

- [ ] **Step 1: Rewrite `notebooks/01_fetch_data.ipynb`**

Write the file at `C:\Users\Owner\Documents\premier-league-elo\notebooks\01_fetch_data.ipynb`:

```json
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["# 01 — Fetch and Cache Raw Data\n\nStatsBomb: full event data. understat: per-shot xG. fbref (soccerdata): lineups + exact sub timing.\nIdempotent — re-running skips already-cached files."]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import sys, json\n",
    "from pathlib import Path\n",
    "\n",
    "sys.path.insert(0, str(Path('..').resolve()))\n",
    "RAW_DIR = Path('../data/raw')\n",
    "RAW_DIR.mkdir(parents=True, exist_ok=True)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from src.statsbomb_loader import (\n",
    "    get_available_seasons, get_matches, get_starters,\n",
    "    get_substitutions, get_shots, get_player_names\n",
    ")\n",
    "\n",
    "seasons = get_available_seasons()\n",
    "print(seasons)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "for _, season in seasons.iterrows():\n",
    "    season_id = int(season['season_id'])\n",
    "    season_name = season['season_name']\n",
    "    out_file = RAW_DIR / f'sb_matches_{season_id}.json'\n",
    "    if out_file.exists():\n",
    "        print(f'[SKIP] {season_name}')\n",
    "        continue\n",
    "\n",
    "    print(f'[FETCH] {season_name} ...')\n",
    "    matches = get_matches(season_id)\n",
    "    records = []\n",
    "\n",
    "    for _, match in matches.iterrows():\n",
    "        mid = int(match['match_id'])\n",
    "        home = str(match['home_team'])\n",
    "        away = str(match['away_team'])\n",
    "        try:\n",
    "            starters = get_starters(mid)\n",
    "            subs = get_substitutions(mid, home, away)\n",
    "            shots = get_shots(mid)\n",
    "            names = get_player_names(mid)\n",
    "        except Exception as e:\n",
    "            print(f'  [ERROR] match {mid}: {e}')\n",
    "            continue\n",
    "\n",
    "        records.append({\n",
    "            'match_id': f'sb_{mid}',\n",
    "            'date': str(match['match_date']),\n",
    "            'home_team': home,\n",
    "            'away_team': away,\n",
    "            'home_team_id': home,\n",
    "            'away_team_id': away,\n",
    "            'season': season_name,\n",
    "            'source': 'statsbomb',\n",
    "            'starters': starters,\n",
    "            'substitutions': subs,\n",
    "            'shots': shots,\n",
    "            'player_names': names\n",
    "        })\n",
    "\n",
    "    with open(out_file, 'w') as f:\n",
    "        json.dump(records, f)\n",
    "    print(f'  Saved {len(records)} matches to {out_file.name}')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["## understat seasons (shots) + fbref seasons (lineups)\n\nFor each season: pre-fetch fbref lineup data once (cached to disk by soccerdata),\nthen fetch understat shots per match. Lineups come from fbref; shots come from understat.\nFalls back to understat approximate lineups if fbref has no match for a game."]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from src.understat_loader import get_season_results, get_match_shots, parse_shots\n",
    "from src.understat_loader import get_match_roster, parse_starters, parse_substitutions  # fallback\n",
    "from src.fbref_loader import get_season_lineups, normalize_team_name\n",
    "\n",
    "UNDERSTAT_YEARS = [2020, 2021, 2022, 2023, 2024]\n",
    "\n",
    "for year in UNDERSTAT_YEARS:\n",
    "    season_label = f'{year}-{str(year + 1)[-2:]}'\n",
    "    out_file = RAW_DIR / f'us_matches_{year}.json'\n",
    "    if out_file.exists():\n",
    "        print(f'[SKIP] {season_label}')\n",
    "        continue\n",
    "\n",
    "    print(f'[FETCH lineups] {season_label} via fbref ...')\n",
    "    fbref_lineups = get_season_lineups(year)\n",
    "    print(f'  fbref returned {len(fbref_lineups)} matches')\n",
    "\n",
    "    print(f'[FETCH shots] {season_label} via understat ...')\n",
    "    results = get_season_results(year)\n",
    "    records = []\n",
    "    fbref_hits, fallback_hits = 0, 0\n",
    "\n",
    "    for match in results:\n",
    "        mid = int(match['id'])\n",
    "        home_team = match['h']['title']\n",
    "        away_team = match['a']['title']\n",
    "        date_str = match['datetime'][:10]\n",
    "\n",
    "        try:\n",
    "            shots_raw = get_match_shots(mid)\n",
    "        except Exception as e:\n",
    "            print(f'  [ERROR] shots match {mid}: {e}')\n",
    "            continue\n",
    "\n",
    "        home_shots = parse_shots(shots_raw, 'h', home_team, mid)\n",
    "        away_shots = parse_shots(shots_raw, 'a', away_team, mid)\n",
    "\n",
    "        # Look up fbref lineup by normalized match key\n",
    "        match_key = f'{date_str}|{normalize_team_name(home_team)}|{normalize_team_name(away_team)}'\n",
    "        lineup = fbref_lineups.get(match_key)\n",
    "\n",
    "        if lineup:\n",
    "            home_starters = lineup['home_starters']\n",
    "            away_starters = lineup['away_starters']\n",
    "            subs = lineup['substitutions']\n",
    "            player_names = lineup['player_names']\n",
    "            fbref_hits += 1\n",
    "        else:\n",
    "            # Fallback: understat approximate lineups\n",
    "            try:\n",
    "                roster_raw = get_match_roster(mid)\n",
    "            except Exception as e:\n",
    "                print(f'  [WARN] roster fallback failed match {mid}: {e}')\n",
    "                continue\n",
    "            home_starters = parse_starters(roster_raw, 'h')\n",
    "            away_starters = parse_starters(roster_raw, 'a')\n",
    "            subs = (\n",
    "                parse_substitutions(roster_raw, 'h', home_team)\n",
    "                + parse_substitutions(roster_raw, 'a', away_team)\n",
    "            )\n",
    "            player_names = {\n",
    "                f\"us_{p['id']}\": p['player']\n",
    "                for p in roster_raw.get('h', []) + roster_raw.get('a', [])\n",
    "            }\n",
    "            fallback_hits += 1\n",
    "\n",
    "        records.append({\n",
    "            'match_id': f'us_{mid}',\n",
    "            'date': date_str,\n",
    "            'home_team': home_team,\n",
    "            'away_team': away_team,\n",
    "            'home_team_id': home_team,\n",
    "            'away_team_id': away_team,\n",
    "            'season': season_label,\n",
    "            'source': 'understat',\n",
    "            'starters': {home_team: home_starters, away_team: away_starters},\n",
    "            'substitutions': subs,\n",
    "            'shots': home_shots + away_shots,\n",
    "            'player_names': player_names\n",
    "        })\n",
    "\n",
    "    with open(out_file, 'w') as f:\n",
    "        json.dump(records, f)\n",
    "    print(f'  Saved {len(records)} matches (fbref: {fbref_hits}, fallback: {fallback_hits})')\n",
    "\n",
    "print('Done!')"
   ]
  }
 ],
 "metadata": {\n  \"kernelspec\": {\"display_name\": \"Python 3\", \"language\": \"python\", \"name\": \"python3\"},\n  \"language_info\": {\"name\": \"python\", \"version\": \"3.8.8\"}\n },\n \"nbformat\": 4,\n \"nbformat_minor\": 4\n}
```

- [ ] **Step 2: Commit**

```bash
git add notebooks/01_fetch_data.ipynb
git commit -m "feat: use fbref lineups in understat fetch cell, keep understat for shots"
git push origin main
```

- [ ] **Step 3: Run the notebook to verify end-to-end**

Open Jupyter: `jupyter notebook notebooks/01_fetch_data.ipynb`

Delete stale cache files first:
```powershell
Remove-Item "C:\Users\Owner\Documents\premier-league-elo\data\raw\us_matches_*.json"
```

Then run all cells. For the understat+fbref cell, look for:
- `fbref returned 380 matches` (or similar) for each season
- Final line per season: `Saved 380 matches (fbref: 370+, fallback: <10)` — a high fbref hit rate confirms team name normalization is working

If `fallback` count is unexpectedly high (>20 per season), the team name alias dict in `normalize_team_name` likely needs additional entries. Print the missed keys by temporarily adding:
```python
if not lineup:
    print(f'  [MISS] {match_key}')
```
...and add the missing mappings to `_ALIASES` in `src/fbref_loader.py`.
