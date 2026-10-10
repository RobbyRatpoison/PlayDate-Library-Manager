"""The Library's game list as its own cacheable file: the database fingerprint, the key, the
server-side cache, and that the body rebuilds exactly the games the page used to get inline."""
import json
import sqlite3

import pytest
from flask import Flask

import config
import database
import library


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / 'games.db')
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE games (appid INTEGER PRIMARY KEY, name TEXT, platform TEXT, groups TEXT, tags TEXT,
                    duplicate_of TEXT, last_played INTEGER, date_added INTEGER, release_date INTEGER, icon_hash TEXT)""")
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (10, 'Beta',  'steam', 'a,b', 'rpg,indie', None, 1700000000, 1600000000, None, 'abc'),
        (-5, 'alpha', 'gog',   None,  'indie',     None, None,       None,       1500000000, None),
    ])
    conn.commit()
    conn.close()

    def open_conn():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c
    monkeypatch.setattr(database, '_db', lambda: path)
    monkeypatch.setattr(library, 'get_db', open_conn)
    library._LIB_CACHE.clear()
    yield path
    library._LIB_CACHE.clear()


def _q(where='1=1', params=None, sort='name COLLATE NOCASE'):
    return {'query': f"SELECT * FROM games WHERE {where} ORDER BY {sort}", 'params': params or [],
            'sort_col': sort, 'sort_ord': ''}


def test_fingerprint_moves_with_every_write_and_not_without(db):
    f1 = database.db_fingerprint()
    assert database.db_fingerprint() == f1                       # reading the stamp changes nothing
    conn = sqlite3.connect(db)
    conn.execute("UPDATE games SET name = 'Gamma' WHERE appid = 10")
    conn.commit()
    f2 = database.db_fingerprint()
    assert f2 != f1                                              # a committed write moves it (WAL or main file)
    assert database.db_fingerprint() == f2
    conn.close()


def test_key_changes_with_query_params_database_and_build(monkeypatch):
    base = library._library_key(_q(), ('p', 1, 2, 3, 4))
    assert library._library_key(_q(), ('p', 1, 2, 3, 4)) == base
    assert library._library_key(_q("platform = ?", ['gog']), ('p', 1, 2, 3, 4)) != base
    assert library._library_key(_q(params=['x']), ('p', 1, 2, 3, 4)) != base
    assert library._library_key(_q(sort='appid'), ('p', 1, 2, 3, 4)) != base
    assert library._library_key(_q(), ('p', 1, 2, 3, 5)) != base           # database stamp
    monkeypatch.setattr(config, '__build__', 'another-build')
    assert library._library_key(_q(), ('p', 1, 2, 3, 4)) != base           # app build


def test_body_rebuilds_the_games_the_page_used_to_get(db):
    app = Flask('t')
    with app.app_context():
        res = library._library_result(_q(), 'k1')
    d = json.loads(res['body'])
    games = [dict(zip(d['cols'], r)) for r in d['rows']]
    assert [g['name'] for g in games] == ['alpha', 'Beta']                      # NOCASE order kept
    assert 'icon_hash' not in games[0]                                          # dropped, as before
    assert games[1]['last_played'] == database.ts_to_date(1700000000)           # dates as YYYY-MM-DD strings
    assert games[0]['last_played'] is None and games[0]['release_date'] == database.ts_to_date(1500000000)
    assert d['cols'] == sorted(d['cols'])                                        # same key order tojson gave
    assert res['appids'] == [-5, 10] and res['count'] == 2 and res['total_games'] == 2
    assert res['groups'] == ['a', 'b'] and res['tags'] == ['indie', 'rpg'] and res['platforms'] == ['gog', 'steam']


def test_result_is_cached_by_key_and_old_entries_are_evicted(db):
    app = Flask('t')
    with app.app_context():
        first = library._library_result(_q(), 'k0')
        assert library._library_result(_q(), 'k0') is first                      # served from the cache
        for i in range(1, library._LIB_CACHE_MAX + 1):
            library._library_result(_q(), f'k{i}')
    assert 'k0' not in library._LIB_CACHE                                        # least recently used went first
    assert len(library._LIB_CACHE) == library._LIB_CACHE_MAX


def test_a_failed_query_falls_back_and_is_never_cached(db):
    app = Flask('t')
    with app.app_context():
        res = library._library_result(_q(where='no_such_column = 1'), 'bad')
    assert res['sql_error'] and res['count'] == 2                               # fell back to every game
    assert 'bad' not in library._LIB_CACHE


def test_prewarm_returns_the_key_the_library_page_embeds_and_writes_nothing(db, monkeypatch):
    app = Flask('t')
    app.register_blueprint(library.library_bp)
    monkeypatch.setattr(library, 'load_state', lambda: {})
    monkeypatch.setattr(library, '_library_query', lambda state: _q())
    before = database.db_fingerprint()
    with app.test_request_context():
        resp = library.library_prewarm()
        url = resp.get_json()['url']
        _, key, _ = library._library_current({})
    assert resp.get_json()['status'] == 'ok' and url.endswith('k=' + key)
    assert database.db_fingerprint() == before                                  # read-only


def test_prewarm_waits_while_a_bulk_job_runs(db, monkeypatch):
    app = Flask('t')
    monkeypatch.setitem(library._bulk_op_state, 'running', True)
    with app.test_request_context():
        assert library.library_prewarm().get_json() == {'status': 'busy'}


def test_order_route_lists_the_current_appids_in_sort_order(db, monkeypatch):
    app = Flask('t')
    state = {'sort': 'name', 'order': 'DESC'}
    monkeypatch.setattr(library, 'load_state', lambda: state)
    monkeypatch.setattr(library, '_library_query', lambda st: _q(sort='appid ' + st['order']))
    with app.test_request_context():
        d = library.library_order().get_json()
    assert d == {'status': 'ok', 'appids': [10, -5], 'sort': 'name', 'order': 'DESC'}
