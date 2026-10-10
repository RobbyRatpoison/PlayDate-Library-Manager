"""The bulk art job's source choice for non-Steam games: 'steam' means the game's Steam copy (duplicate
link, else the backfill match; nothing else), 'sgdb' is passed through as a strict source, 'auto' keeps the library's order."""
import sqlite3

import pytest

import database
import images
import scrapers


@pytest.fixture
def job(tmp_path, monkeypatch):
    path = str(tmp_path / 'games.db')
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE games (appid INTEGER PRIMARY KEY, name TEXT, platform TEXT,
                    duplicate_of TEXT, steam_appid INTEGER, icon_hash TEXT)""")
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?)", [
        (620, 'Portal 2', 'steam', None, None, 'abc'),
        (-1, 'Portal 2', 'epic_games', '620', None, None),      # linked duplicate
        (-2, 'Solo',     'epic_games', None, None, None),       # no Steam copy
        (-3, 'Guessed',  'epic_games', None, 620, None),        # backfill match only, no link
    ])
    conn.commit()
    conn.close()

    def open_conn():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c
    monkeypatch.setattr(database, 'get_db', open_conn)
    monkeypatch.setattr(scrapers, 'get_db', open_conn)
    monkeypatch.setattr(scrapers.time, 'sleep', lambda s: None)
    monkeypatch.setattr(scrapers, '_sgdb_search_game_id', lambda name: 111)
    log = {'updates': {}, 'steam': [], 'calls': []}
    monkeypatch.setattr(scrapers, 'update_game_data', lambda appid, **kw: log['updates'].setdefault(appid, {}).update(kw))
    monkeypatch.setattr(scrapers, 'download_from_steam',
                        lambda appid, steam_appid, kind, icon_hash='': log['steam'].append((appid, steam_appid, kind)) or
                        ('missing' if kind == 'icon' else 'steam'))

    def fake(kind):
        def run(appid, *a, **kw):
            log['calls'].append((kind, appid, kw.get('source', 'default')))
            return 'sgdb_grid'
        return run
    for kind in ('vertical', 'horizontal', 'icon'):
        monkeypatch.setattr(scrapers, f'download_{kind}', fake(kind))
    return log


def _run(source, appids, types=('vertical', 'horizontal', 'icon')):
    seen = []
    counts = scrapers.bulk_art_scrape_games(appids, list(types), source, None, lambda ev, a, t: seen.append((ev, a)))
    return counts, seen


def test_steam_uses_the_linked_copy_and_only_for_what_it_finds(job):
    counts, _ = _run('steam', [-1])
    assert counts == {'done': 1, 'failed': 0}
    assert job['updates'][-1]['vertical_art_source'] == 'steam' and job['updates'][-1]['horizontal_art_source'] == 'steam'
    assert 'icon_source' not in job['updates'][-1]                 # nothing found for the icon: left as it was
    assert (-1, 620, 'horizontal') in job['steam'] and not job['calls']   # no other source was asked


def test_steam_falls_back_to_the_backfill_match_when_there_is_no_duplicate_link(job):
    counts, _ = _run('steam', [-3], types=('horizontal',))
    assert counts == {'done': 1, 'failed': 0} and job['steam'] == [(-3, 620, 'horizontal')]


def test_steam_fails_a_game_with_no_steam_copy_without_touching_it(job):
    counts, seen = _run('steam', [-2])
    assert counts == {'done': 0, 'failed': 1}
    assert job['updates'] == {} and job['steam'] == [] and job['calls'] == []
    assert ('failed', -2) in seen


def test_steam_respects_the_chosen_types(job):
    _run('steam', [-1], types=('horizontal',))
    assert job['steam'] == [(-1, 620, 'horizontal')]
    assert set(job['updates'][-1]) == {'horizontal_art_source', 'art_fetched'}


def test_sgdb_is_passed_through_as_a_strict_source(job):
    _run('sgdb', [-1], types=('vertical', 'horizontal'))
    assert job['calls'] == [('vertical', -1, 'sgdb'), ('horizontal', -1, 'sgdb')]


def test_auto_leaves_the_librarys_own_order_alone(job):
    _run('auto', [-1], types=('horizontal',))
    assert job['calls'] == [('horizontal', -1, 'default')] and job['steam'] == []


def test_the_duplicate_link_wins_over_the_backfill_match(job):
    conn = database.get_db()
    conn.execute("INSERT INTO games VALUES (730, 'Other', 'steam', NULL, NULL, '')")
    conn.execute("UPDATE games SET steam_appid = 730 WHERE appid = -1")      # -1 is linked to 620 as a duplicate
    conn.commit()
    conn.close()
    assert images.steam_copy_of(-1)['steam_appid'] == 620
