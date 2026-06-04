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
