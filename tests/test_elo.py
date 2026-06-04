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


def test_process_match_sub_changes_who_receives_xg():
    # p5 comes on for p1 at minute 65; shot at minute 70 should credit p5, not p1
    ratings = {f'p{i}': 1000.0 for i in range(1, 7)}
    subs = [{'minute': 65, 'player_off_id': 'p1', 'player_on_id': 'p5', 'team_id': 'home'}]
    xg_events = [
        {'minute': 30, 'xg': 0.3, 'shooting_team_id': 'home'},   # p1 on pitch
        {'minute': 70, 'xg': 0.2, 'shooting_team_id': 'home'},   # p5 on pitch, p1 off
    ]
    _, deltas = process_match(
        ratings=ratings,
        home_team_id='home',
        away_team_id='away',
        home_starters=['p1', 'p2'],
        away_starters=['p3', 'p4'],
        substitutions=subs,
        xg_events=xg_events,
    )
    assert abs(deltas['p1'] - 0.3) < 1e-9   # only minute-30 shot
    assert abs(deltas['p5'] - 0.2) < 1e-9   # only minute-70 shot
    assert abs(deltas['p2'] - 0.5) < 1e-9   # both shots (never subbed)
