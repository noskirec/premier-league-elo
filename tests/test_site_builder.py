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
