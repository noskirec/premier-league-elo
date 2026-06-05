# fbref Lineup Swap — Design Spec

**Date:** 2026-06-04
**Status:** Approved

---

## Overview

Replace understat as the source of lineup and substitution data with fbref (via the `soccerdata` Python library). understat continues to provide per-shot xG data. The two sources contribute independent, non-overlapping streams — no cross-source player matching is required.

---

## Motivation

understat infers substitution timing from "minutes played" rather than providing the exact minute. This produces ±5-minute approximations that reduce the accuracy of which players are credited/debited for xG events near a substitution. fbref records the exact minute of every substitution from official match data.

---

## Data Source Responsibilities After the Change

| Source | Provides | Player ID prefix |
|---|---|---|
| fbref (`soccerdata`) | Starting lineups, exact sub minutes, player names | `fb_` |
| understat | Per-shot xG value, shot minute, shooting team | — |
| StatsBomb | Unchanged — historical PL seasons as before | `sb_` |

The `shooter_player_id` field on `xg_events` is set to `None` for all understat-sourced matches (it was optional/unused in ELO calculation). No player matching between fbref and understat IDs is needed — `process_match()` only uses `shooting_team_id` and `minute` from shot events.

---

## New Module: `src/fbref_loader.py`

### `normalize_team_name(name: str) -> str`

Lowercases the name, strips common suffixes ("FC", "AFC"), and applies a small alias dict for known fbref↔understat divergences (e.g. "wolverhampton wanderers" → "wolves", "brighton & hove albion" → "brighton"). Used to build match lookup keys.

### `get_season_lineups(season_year: int) -> Dict[str, Dict]`

Pre-fetches all lineup data for one EPL season using `soccerdata.FBref`. Internally calls `fbref.read_schedule()` and `fbref.read_lineup()` — both responses are cached to disk by soccerdata on first run (subsequent calls are instant).

Returns a dict keyed by normalized match key:

```
"{date}|{normalize_team_name(home)}|{normalize_team_name(away)}"
```

Each value:

```python
{
  'home_starters': ['fb_abc', ...],     # 11 fb_ player IDs
  'away_starters': ['fb_xyz', ...],
  'substitutions': [
    {
      'minute': 61,
      'player_off_id': 'fb_abc',
      'player_on_id': 'fb_def',
      'team_id': 'Arsenal'            # team name string, matches home_team/away_team
    },
    ...
  ],
  'player_names': {'fb_abc': 'Bukayo Saka', ...}
}
```

`team_id` in substitution dicts uses the full team name string (not normalized) so it matches `home_team`/`away_team` in the match record, which is what `process_match()` receives as `home_team_id`/`away_team_id`.

---

## Modified Module: `src/understat_loader.py`

Remove from the primary data path:
- `get_match_roster()` — no longer called in main notebook flow
- `parse_starters()` — no longer called in main notebook flow
- `parse_substitutions()` — no longer called in main notebook flow

**Keep** all three functions as fallback (called when fbref has no match for a given game). Keep `get_season_results()`, `get_match_shots()`, and `parse_shots()` unchanged — these are the shot data path.

---

## Updated Notebook: `notebooks/01_fetch_data.ipynb`

### Understat season cell — new structure

For each understat season year:

1. **Pre-fetch fbref lineups** (new cell, runs once per season):
   ```python
   fbref_lineups = get_season_lineups(year)
   ```

2. **Per-match loop** — for each match from `get_season_results(year)`:
   - Fetch shots from understat (`get_match_shots`) — unchanged
   - Build normalized match key from date + team names
   - **If key found in `fbref_lineups`**: use fbref starters, subs, player_names
   - **If key not found** (rare): fall back to `get_match_roster` + `parse_starters` + `parse_substitutions`
   - Set `shooter_player_id` to `None` for all shots (since fbref player IDs are in a separate namespace from understat shot player IDs, and the field is not used in ELO)

3. Match record format is unchanged — same keys as today, just populated from fbref instead of understat for lineup fields.

---

## `requirements.txt`

Add:
```
soccerdata>=0.3
```

Keep `aiohttp>=3.9.0` and `nest-asyncio>=1.6.0` — still needed for understat shot fetching.

---

## Files Changed

| File | Change |
|---|---|
| `src/fbref_loader.py` | **New** — normalize_team_name + get_season_lineups |
| `src/understat_loader.py` | No code changes; parse_starters/parse_substitutions/get_match_roster demoted to fallback-only |
| `notebooks/01_fetch_data.ipynb` | Updated understat cells to pre-fetch fbref lineups and use them in the match loop |
| `requirements.txt` | Add soccerdata>=0.3 |

## Files Unchanged

`src/db.py`, `src/elo.py`, `src/site_builder.py`, `src/statsbomb_loader.py`, `notebooks/02_calculate_elo.ipynb`, `notebooks/03_build_site.ipynb`, all tests.

---

## Out of Scope

- Backfilling existing `data/elo.db` — existing cached raw JSON files will be re-fetched on next notebook run with fbref lineups
- Matching fbref and understat player IDs — not needed for current ELO model
- Adding `shooter_player_id` population — future enhancement
