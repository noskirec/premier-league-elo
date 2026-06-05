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
