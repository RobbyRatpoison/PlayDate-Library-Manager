"""compute_tag_affinity: the per-tag taste affinity behind tag similarity and the
Tuning modal's liked / disliked tag lists."""
import sqlite3

import pytest

import database


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE games (appid INTEGER PRIMARY KEY, platform TEXT, tags TEXT, "
              "completion_status TEXT, playtime_forever INTEGER)")
    rows = [
        (1, 'steam', 'RPG,Story', 'Beaten', 6000),
        (2, 'steam', 'RPG,Puzzle', 'Completed', 6000),
        (3, 'steam', 'Shooter', 'Never Played', 0),
        (4, 'steam', 'Shooter', 'Never Played', 0),
        (5, 'steam', 'Shooter,RPG', 'Never Played', 0),
        (6, 'epic_games', 'Windows', 'Beaten', 600),   # non-Steam: ignored
    ]
    c.executemany("INSERT INTO games VALUES (?,?,?,?,?)", rows)
    yield c
    c.close()


def test_liked_and_avoided_tags(conn):
    aff = database.compute_tag_affinity(conn, 2.0, 60)
    assert aff['Story'] > 0 and aff['RPG'] > 0
    assert aff['Shooter'] < 0
    assert 'Windows' not in aff


def test_rare_tag_floor_excludes_tags(conn):
    assert 'Story' in database.compute_tag_affinity(conn, 2.0, 60)
    assert 'Story' not in database.compute_tag_affinity(conn, 50.0, 60)


def test_playtime_cap_changes_weighting(conn):
    conn.execute("UPDATE games SET playtime_forever = 30 WHERE appid = 2")
    low = database.compute_tag_affinity(conn, 2.0, 1)['Story']
    high = database.compute_tag_affinity(conn, 2.0, 200)['Story']
    assert low != high


def test_overrides_pin_ignore_and_unknown_tags(conn):
    base = database.compute_tag_affinity(conn, 2.0, 60)
    out = database.compute_tag_affinity(conn, 2.0, 60, {
        'Shooter': 'ignore', 'Story': 'dislike', 'Metroidvania': 'like'})
    assert out['Shooter'] == 0.0
    assert out['Story'] < 0
    assert out['Metroidvania'] > 0          # pinned even though no game carries it
    assert out['RPG'] == base['RPG']        # untouched


def test_pins_fall_back_when_no_computed_strength():
    out = database.apply_tag_overrides({}, {'A': 'like', 'B': 'dislike'})
    assert out == {'A': 0.25, 'B': -0.25}


def test_normalize_tag_overrides():
    from config import normalize_tag_overrides
    assert normalize_tag_overrides({' RPG ': 'like', 'a,b': 'like', 'X': 'bogus', 3: 'like'}) == {'RPG': 'like'}
    assert normalize_tag_overrides(None) == {}
