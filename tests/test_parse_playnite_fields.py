"""Playnite Last Played / Time Played extraction (imports.parse_playnite_fields) against a
synthetic LiteDB-shaped games.db. As with test_parse_playnite_dates.py, no real backup was
available: this checks the pairing logic (a game without a field must not take its
neighbour's value) and the BSON decoding, not Playnite's real on-disk layout.
"""
import struct
import zipfile

import imports

DAY_MS = 86_400_000


def _gameid(value):
    b = value.encode() + b'\x00'
    return b'\x02GameId\x00' + struct.pack('<i', len(b)) + b


def _dt(name, ms):
    return b'\x09' + name.encode() + b'\x00' + struct.pack('<q', ms)


def _playtime64(seconds):
    return b'\x12Playtime\x00' + struct.pack('<q', seconds)


def _playtime32(seconds):
    return b'\x10Playtime\x00' + struct.pack('<i', seconds)


def _zip(tmp_path, blob):
    p = tmp_path / 'backup.zip'
    with zipfile.ZipFile(p, 'w') as zf:
        zf.writestr('library/games.db', blob)
    return str(p)


def test_reads_all_three_fields(tmp_path):
    blob = (
        b'\x00' * 50 + _gameid('440') + b'\x00' * 20
        + _dt('Added', 1_600_000_000_000) + _dt('LastActivity', 1_650_000_000_000)
        + _playtime64(7200)
    )
    r = imports.parse_playnite_fields(_zip(tmp_path, blob))
    assert r == {440: {'date_added': '2020-09-13', 'last_played': 1_650_000_000, 'playtime': 120}}


def test_int32_playtime_is_accepted(tmp_path):
    blob = _gameid('10') + b'\x00' * 20 + _playtime32(600)
    assert imports.parse_playnite_fields(_zip(tmp_path, blob)) == {10: {'playtime': 10}}


def test_game_without_field_does_not_take_neighbours_value(tmp_path):
    # Game 1 has a LastActivity; game 2 (right after it) has none. Game 2 must not
    # borrow game 1's even though it is well inside the window.
    blob = (
        _gameid('1') + b'\x00' * 30 + _dt('LastActivity', 1_650_000_000_000)
        + b'\x00' * 300 + _gameid('2') + b'\x00' * 30
    )
    r = imports.parse_playnite_fields(_zip(tmp_path, blob))
    assert r[1]['last_played'] == 1_650_000_000
    assert 'last_played' not in r.get(2, {})


def test_zero_playtime_and_out_of_range_dates_are_skipped(tmp_path):
    blob = _gameid('5') + b'\x00' * 20 + _playtime64(0) + _dt('LastActivity', 0)
    assert imports.parse_playnite_fields(_zip(tmp_path, blob)) == {}


def test_occurrence_beyond_window_is_ignored(tmp_path):
    blob = _gameid('7') + b'\x00' * (imports._PLAYNITE_WINDOW + 100) + _playtime64(3600)
    assert imports.parse_playnite_fields(_zip(tmp_path, blob)) == {}


def test_no_games_db_returns_empty(tmp_path):
    p = tmp_path / 'x.zip'
    with zipfile.ZipFile(p, 'w') as zf:
        zf.writestr('other.txt', b'hi')
    assert imports.parse_playnite_fields(str(p)) == {}
