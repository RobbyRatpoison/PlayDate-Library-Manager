"""Duplicate hiding: the platform priority order decides which copy of a game is
shown. A link made by hand only says two games are the same game -- it never
overrides that order, and it must never leave both copies hidden."""
import sqlite3

import pytest

import database


@pytest.fixture
def games_db(tmp_path, monkeypatch):
    path = str(tmp_path / 'games.db')
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE games (appid INTEGER PRIMARY KEY, name TEXT, platform TEXT, "
                 "duplicate_of TEXT, duplicate_auto INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

    def open_db():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c
    monkeypatch.setattr(database, 'get_db', open_db)
    return open_db


def add(db, appid, name, platform):
    c = db()
    c.execute("INSERT INTO games (appid, name, platform) VALUES (?, ?, ?)", (appid, name, platform))
    c.commit()
    c.close()


def link_by_hand(db, appid, target):
    """What the Duplicate of row saves: a manual (duplicate_auto = 0) link."""
    c = db()
    c.execute("UPDATE games SET duplicate_of = ?, duplicate_auto = 0 WHERE appid = ?", (str(target), appid))
    c.commit()
    c.close()


def visible(db):
    c = db()
    rows = c.execute("SELECT appid FROM games WHERE duplicate_of IS NULL OR duplicate_of = '' ORDER BY appid").fetchall()
    c.close()
    return [r['appid'] for r in rows]


def test_same_name_shows_the_higher_priority_platform(games_db):
    add(games_db, 1, 'Hades', 'steam')
    add(games_db, -1, 'Hades', 'gog')
    database.auto_detect_duplicates(['steam', 'gog'])
    assert visible(games_db) == [1]
    database.auto_detect_duplicates(['gog', 'steam'])
    assert visible(games_db) == [-1]


def test_linking_against_the_priority_order_does_not_hide_both(games_db):
    add(games_db, 1, 'Hades', 'steam')
    add(games_db, -1, 'Hades', 'gog')
    database.auto_detect_duplicates(['steam', 'gog'])
    # The user opens the visible Steam copy and links it to the GOG copy.
    link_by_hand(games_db, 1, -1)
    database.auto_detect_duplicates(['steam', 'gog'])
    assert visible(games_db) == [1]          # priority still wins; the game is not lost


def test_manual_link_between_differently_named_games_follows_priority(games_db):
    add(games_db, 2, 'The Witcher 3', 'steam')
    add(games_db, -2, 'Witcher 3: Wild Hunt', 'gog')
    link_by_hand(games_db, -2, 2)            # made from the GOG copy, pointing at Steam
    database.auto_detect_duplicates(['steam', 'gog'])
    assert visible(games_db) == [2]
    # Made the other way round (from the higher-priority copy): still ends up hiding the lower one.
    c = games_db(); c.execute("UPDATE games SET duplicate_of = NULL"); c.commit(); c.close()
    link_by_hand(games_db, 2, -2)
    database.auto_detect_duplicates(['steam', 'gog'])
    assert visible(games_db) == [2]


def test_manual_link_is_re_pointed_when_the_priority_order_changes(games_db):
    add(games_db, 2, 'The Witcher 3', 'steam')
    add(games_db, -2, 'Witcher 3: Wild Hunt', 'gog')
    link_by_hand(games_db, -2, 2)
    database.auto_detect_duplicates(['steam', 'gog'])
    assert visible(games_db) == [2]
    database.auto_detect_duplicates(['gog', 'steam'])
    assert visible(games_db) == [-2]


def test_detection_is_stable_when_run_repeatedly(games_db):
    add(games_db, 1, 'Hades', 'steam')
    add(games_db, -1, 'Hades', 'gog')
    link_by_hand(games_db, 1, -1)
    for _ in range(3):
        database.auto_detect_duplicates(['steam', 'gog'])
        assert visible(games_db) == [1]


def test_link_within_one_platform_is_left_alone(games_db):
    add(games_db, -3, 'Some Game', 'gog')
    add(games_db, -4, 'Some Game (Copy)', 'gog')
    link_by_hand(games_db, -4, -3)
    database.auto_detect_duplicates(['steam', 'gog'])
    assert visible(games_db) == [-3]




PRIORITY = ['steam', 'epic_games', 'gog']


def _db(sql):
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(sql)
    return conn


def _listed(sql, where, params=()):
    """Appids a page would list for `where`, with "Hide duplicate entries" on."""
    where, params = database.hide_duplicates_where(where, list(params), PRIORITY)
    conn = _db(sql)
    rows = conn.execute(f"SELECT appid FROM games WHERE {where} ORDER BY appid", params).fetchall()
    conn.close()
    return [r['appid'] for r in rows]


_COLS = ("CREATE TABLE games (appid INTEGER PRIMARY KEY, name TEXT, platform TEXT, tags TEXT, "
         "completion_status TEXT, duplicate_of TEXT, duplicate_auto INTEGER DEFAULT 0);")
# One game on three stores (Steam 100 is shown, Epic -1 and GOG -2 point at it) and an unrelated game.
THREE = _COLS + """
INSERT INTO games VALUES (100, 'Game', 'steam',      'Puzzle', 'Beaten',       NULL, 0);
INSERT INTO games VALUES (-1,  'Game', 'epic_games', 'Action', 'Never Played', '100', 1);
INSERT INTO games VALUES (-2,  'Game', 'gog',        'Action', 'Never Played', '100', 1);
INSERT INTO games VALUES (200, 'Other','steam',      'Action', 'Never Played', NULL, 0);
"""
TWO = _COLS + """
INSERT INTO games VALUES (100, 'Game', 'steam',      'Puzzle', 'Beaten',       NULL, 0);
INSERT INTO games VALUES (-1,  'Game', 'epic_games', 'Action', 'Never Played', '100', 1);
INSERT INTO games VALUES (200, 'Other','steam',      'Action', 'Never Played', NULL, 0);
"""


def test_only_the_top_copy_shows_without_a_filter():
    assert _listed(THREE, '1=1') == [100, 200]
    assert _listed(TWO, "platform != 'gog'") == [100, 200]


def test_excluding_the_top_copy_shows_only_the_next_priority_one():
    # Steam excluded, Epic and GOG both allowed: Epic (second) shows, GOG (third) does not.
    assert _listed(THREE, "platform != 'steam'") == [-1]
    assert _listed(THREE, "platform NOT IN (?)", ['steam']) == [-1]


def test_excluding_a_middle_copy_leaves_the_top_to_hide_the_last():
    assert _listed(THREE, "platform != 'epic_games'") == [100, 200]


def test_the_lowest_copy_shows_when_every_better_one_is_excluded():
    assert _listed(THREE, "platform NOT IN (?, ?)", ['steam', 'epic_games']) == [-2]
    assert _listed(THREE, "platform = 'gog'") == [-2]
    assert _listed(THREE, "platform = 'epic_games'") == [-1]


def test_any_filter_counts_not_just_platform():
    # Only the Epic and GOG copies are tagged Action; Epic ranks higher, so it shows alone.
    assert _listed(THREE, "tags = 'Action'") == [-1, 200]
    assert _listed(THREE, "tags = 'Puzzle'") == [100]
    assert _listed(TWO, "completion_status = 'Never Played'") == [-1, 200]
    # Epic fails the filter too: GOG is the best copy left.
    assert _listed(THREE.replace("'Action', 'Never Played', '100', 1);\nINSERT INTO games VALUES (-2",
                                 "'Racing', 'Never Played', '100', 1);\nINSERT INTO games VALUES (-2"),
                   "tags = 'Action'") == [-2, 200]


def test_an_ungrouped_game_is_unaffected():
    assert _listed(THREE, "name = 'Other'") == [200]


def test_parameters_are_repeated_for_the_subquery():
    where, params = database.hide_duplicates_where("platform = ? AND tags LIKE ?", ['steam', '%x%'], PRIORITY)
    assert params == ['steam', '%x%'] * 3
    assert where.count('?') == len(params)
    assert database.hide_duplicates_where('1=1', ['a'], PRIORITY) == ("(duplicate_of IS NULL OR duplicate_of = '')", ['a'])


def test_platform_missing_from_the_priority_ranks_last():
    sql = _COLS + """
    INSERT INTO games VALUES (100, 'G', 'steam',   'x', 'x', NULL, 0);
    INSERT INTO games VALUES (-1,  'G', 'newplat', 'x', 'x', '100', 1);
    INSERT INTO games VALUES (-2,  'G', 'gog',     'x', 'x', '100', 1);
    """
    assert _listed(sql, "platform != 'steam'") == [-2]


def test_chained_links_are_flattened_to_the_shown_copy():
    conn = _db(_COLS + """
    INSERT INTO games VALUES (100, 'G', 'steam',      'x', 'x', NULL, 0);
    INSERT INTO games VALUES (-1,  'G', 'epic_games', 'x', 'x', '100', 1);
    INSERT INTO games VALUES (-2,  'G', 'humble',     'x', 'x', '-1', 1);
    INSERT INTO games VALUES (-3,  'G', 'gog',        'x', 'x', '-2', 1);
    """)
    database._flatten_duplicate_links(conn)
    got = {r['appid']: r['duplicate_of'] for r in conn.execute("SELECT appid, duplicate_of FROM games")}
    assert got == {100: None, -1: '100', -2: '100', -3: '100'}
    conn.close()


def test_flatten_survives_a_cycle():
    conn = _db(_COLS + """
    INSERT INTO games VALUES (1, 'G', 'steam', 'x', 'x', '2', 0);
    INSERT INTO games VALUES (2, 'G', 'gog',   'x', 'x', '1', 0);
    """)
    database._flatten_duplicate_links(conn)        # must terminate
    conn.close()
