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
    name = "Wolverhampton Wanderers"
    assert normalize_team_name(normalize_team_name(name)) == normalize_team_name(name)
