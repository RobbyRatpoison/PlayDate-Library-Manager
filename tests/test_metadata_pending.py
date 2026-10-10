"""Which games the automatic startup metadata sweep picks up."""
import sqlite3

import scrapers


def _picked(rows):
    c = sqlite3.connect(':memory:')
    c.execute("""CREATE TABLE games (appid INTEGER, name TEXT, developers TEXT, genres TEXT, tags TEXT,
                 steam_appid INTEGER, meta_backfill_fetched TEXT)""")
    c.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?)", rows)
    return sorted(r[0] for r in c.execute(f"SELECT appid FROM games WHERE {scrapers._METADATA_PENDING_WHERE}"))


FULL = ('Dev', 'Indie', 'Cozy')


def test_a_complete_non_steam_game_with_no_steam_match_is_picked_up():
    assert _picked([(-1, 'Bo', *FULL, None, None)]) == [-1]
    assert _picked([(-2, 'Bo', *FULL, None, '0')]) == [-2]


def test_games_already_matched_or_already_tried_are_not():
    assert _picked([(-1, 'a', *FULL, 620, None)]) == []                     # has a Steam match
    assert _picked([(-2, 'b', *FULL, None, '2026-08-28')]) == []            # tried, nothing found
    assert _picked([(-3, 'c', *FULL, None, 'no_match')]) == []
    assert _picked([(-4, 'd', *FULL, None, 'unconfirmed')]) == []           # parked for a manual confirm


def test_incomplete_games_are_still_picked_up_whatever_their_platform():
    assert _picked([(-1, 'a', '', 'Indie', 'Cozy', 620, None)]) == [-1]
    assert _picked([(10, 'steam game', 'Dev', '', 'Cozy', None, None)]) == [10]


def test_a_complete_steam_game_is_not_picked_up():
    assert _picked([(10, 'steam game', *FULL, None, None)]) == []           # steam_appid is only for non-Steam rows


def test_the_manual_bulk_gate_also_retries_games_already_tried():
    c = sqlite3.connect(':memory:')
    c.execute("""CREATE TABLE games (appid INTEGER, developers TEXT, genres TEXT, tags TEXT,
                 steam_appid INTEGER, meta_backfill_fetched TEXT)""")
    c.executemany("INSERT INTO games VALUES (?,?,?,?,?,?)", [
        (-1, 'D', 'G', 'T', None, None),            # complete, unmatched, never tried
        (-2, 'D', 'G', 'T', None, '2026-08-28'),    # complete, unmatched, tried before: an explicit run retries it
        (-3, 'D', 'G', 'T', None, 'no_match'),
        (-4, 'D', 'G', 'T', 620,  '2026-08-28'),    # complete and matched: nothing to find
        (-5, '',  'G', 'T', 620,  '2026-08-28'),    # incomplete
        (10, 'D', 'G', 'T', None, None),            # a Steam game that is complete
    ])
    got = sorted(r[0] for r in c.execute(f"SELECT appid FROM games WHERE {scrapers._METADATA_MANUAL_WHERE}"))
    assert got == [-5, -3, -2, -1]
