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
| [StatsBomb open data](https://github.com/statsbomb/open-data) | `statsbombpy` | 2003/04 and 2015/16 PL seasons |
| [understat.com](https://understat.com) | `understat` | All PL seasons from 2020–21, xG + lineup data |

Understat substitution timing is approximate (±5 minutes).

## Running the Pipeline

```bash
pip install -r requirements.txt
```

Run notebooks in order:

1. `notebooks/01_fetch_data.ipynb` — fetches and caches raw data to `data/raw/` (~30–60 min for understat)
2. `notebooks/02_calculate_elo.ipynb` — calculates ELO and writes `data/elo.db`
3. `notebooks/03_build_site.ipynb` — generates `index.html`

Re-running is safe — fetching skips cached files and ELO skips processed matches.

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

## Known Limitations & Future Enhancements

- **GitHub Actions automation:** Weekly workflow to re-run the pipeline and auto-commit refreshed data
- **ELO probabilistic model:** Replace simple xG delta with win-probability formula (low-xG goals score bigger)
- **Position weighting:** Discount xG delta differently for goalkeepers
- **Exact sub timing for understat:** Use a secondary source for precise substitution minutes
