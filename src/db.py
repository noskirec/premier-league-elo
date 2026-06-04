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
    conn.execute("PRAGMA foreign_keys = ON")
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
    # MAX(match_id) as tie-breaker when a player appears in two matches on the same date
    rows = conn.execute("""
        SELECT pr.player_id, pr.rating_after
        FROM player_ratings pr
        INNER JOIN (
            SELECT player_id, MAX(date) AS max_date, MAX(match_id) AS max_match
            FROM player_ratings GROUP BY player_id
        ) latest ON pr.player_id = latest.player_id
               AND pr.date = latest.max_date
               AND pr.match_id = latest.max_match
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
