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
