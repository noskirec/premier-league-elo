# Premier League Player ELO — Design Spec

**Date:** 2026-06-03  
**Status:** Approved

---

## Overview

A public GitHub project that tracks Premier League player ELO ratings over the past 5 seasons. ELO is calculated from xG events: when a shot occurs, all 11 players on the attacking team receive +xG to their rating, and all 11 players on the defending team receive −xG. Ratings accumulate continuously across transfers. A static site deployed to GitHub Pages presents a leaderboard and per-player timeline.

---

## Data Sources

**StatsBomb open data** (via `statsbombpy`): rich event-level data including shot events with xG, freeze frames, and timestamps. Free tier covers roughly 3 Premier League seasons.

**understat.com** (via `understat` Python library): xG per shot, match lineups, and substitution times for all Premier League seasons back to 2014. Broader coverage, less granular than StatsBomb.

Priority: use StatsBomb where available; fall back to understat for remaining seasons/matches. Source is recorded per match in the database.

---

## ELO Model

- All players start at a baseline rating of **1000**.
- For each xG shot event:
  - Determine the 22 players on the pitch at that moment (lineup + substitution timestamps).
  - Add `xg_value` to each of the 11 attacking players' ratings.
  - Subtract `xg_value` from each of the 11 defending players' ratings.
- Ratings are continuous across club transfers — a player's rating carries over when they move teams.
- Transfer events are not stored explicitly; they are derived at query time from match affiliation data.
- **Future enhancement (not in scope):** ELO-style probabilistic update (Option B) where xG surprise value drives rating delta — big gain for low-xG shots that score, penalty for high-xG misses.

---

## Database Schema

Single SQLite file: `data/elo.db`. Committed to the repository so visitors can download and query it directly.

### `players`
| column | type | notes |
|---|---|---|
| player_id | TEXT PK | source-prefixed ID (e.g. `sb_12345`, `us_67890`); same player may have entries from both sources — `01_fetch_data.ipynb` resolves duplicates by name matching and canonicalizes to a single ID |
| name | TEXT | |
| nationality | TEXT | |

### `matches`
| column | type | notes |
|---|---|---|
| match_id | TEXT PK | source-prefixed |
| date | DATE | |
| home_team | TEXT | |
| away_team | TEXT | |
| season | TEXT | e.g. `2022-23` |
| source | TEXT | `statsbomb` or `understat` |

### `xg_events`
| column | type | notes |
|---|---|---|
| event_id | TEXT PK | |
| match_id | TEXT FK | |
| minute | INTEGER | |
| xg_value | REAL | |
| shooting_team | TEXT | |
| shooter_player_id | TEXT | reference to players.player_id |

### `player_ratings`
| column | type | notes |
|---|---|---|
| player_id | TEXT FK | |
| match_id | TEXT FK | |
| date | DATE | denormalized for query convenience |
| rating_after | REAL | ELO after this match |
| rating_delta | REAL | change this match |

---

## Notebooks

| notebook | purpose |
|---|---|
| `notebooks/01_fetch_data.ipynb` | Fetch and cache raw data from StatsBomb and understat locally |
| `notebooks/02_calculate_elo.ipynb` | Run ELO calculation, write results to `data/elo.db` |
| `notebooks/03_build_site.ipynb` | Query DB, generate `index.html` with embedded Plotly charts |

Raw data cached to `data/raw/` (gitignored for size). SQLite DB committed.

---

## Visualization (`index.html`)

Deployed to GitHub Pages. Single self-contained file — no external JS frameworks, works offline.

### Leaderboard (default view)
- Sortable HTML table: player name, current ELO, 30-day ELO delta, sparkline (last 20 matches)
- Filterable by: season, minimum matches played threshold
- Clicking a player row opens the detail view

### Player Detail View
- Plotly line chart: ELO over time (full 5-year window)
- Vertical markers at transfer dates, labeled with club name
- Hover tooltip: match date, opponent, xG delta for that match

---

## Repository Structure

```
premier-league-elo/
├── notebooks/
│   ├── 01_fetch_data.ipynb
│   ├── 02_calculate_elo.ipynb
│   └── 03_build_site.ipynb
├── data/
│   ├── raw/           # gitignored
│   └── elo.db         # committed
├── docs/
│   └── superpowers/specs/
├── index.html         # generated, committed, served by GitHub Pages
├── .gitignore
└── README.md
```

---

## Out of Scope

- Automated data refresh (GitHub Actions) — documented as a future enhancement
- Position/role weighting of xG deltas
- Non-Premier League competitions
- ELO probabilistic model (Option B)
