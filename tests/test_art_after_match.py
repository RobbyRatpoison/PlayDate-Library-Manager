"""A non-Steam game's first Steam match gets it the art the match makes possible, but only for covers
that are missing or the wrong shape, and never ones the user set by hand."""
import sqlite3

import pytest

import images
import metadata


@pytest.fixture
def lib(tmp_path, monkeypatch):
    path = str(tmp_path / 'games.db')
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE games (appid INTEGER PRIMARY KEY, name TEXT, steam_appid INTEGER,
                    vertical_art_source TEXT, horizontal_art_source TEXT)""")
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?)", [
        (-1, 'New match',      None, 'sgdb_grid', 'sgdb_grid_wide'),
        (-2, 'Hand set art',   None, 'custom',    'custom'),
        (-3, 'Already linked', 555,  'sgdb_grid', 'sgdb_grid_wide'),
        (-4, 'Mixed',          None, 'store',     'sgdb_grid_wide'),
        (10, 'A Steam game',   None, 'capsule',   'header'),
    ])
    conn.commit()
    conn.close()

    def open_conn():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c
    written, fetched = [], []
    monkeypatch.setattr(metadata, 'get_db', open_conn)

    def fake_update(appid, **kw):
        written.append((appid, kw))
        cols = {k: v for k, v in kw.items() if k in ('steam_appid', 'vertical_art_source', 'horizontal_art_source')}
        if cols:
            c = sqlite3.connect(path)
            c.execute(f"UPDATE games SET {', '.join(k + '=?' for k in cols)} WHERE appid=?", [*cols.values(), appid])
            c.commit(); c.close()
    monkeypatch.setattr(metadata, 'update_game_data', fake_update)
    monkeypatch.setattr(images, '_sgdb_search_game_id', lambda name: 1)
    monkeypatch.setattr(images, '_art_path', lambda kind, appid: f'{kind}/{appid}')
    fits = {}
    monkeypatch.setattr(images, '_art_fits', lambda path, kind: fits.get(path, False))
    for kind in ('vertical', 'horizontal'):
        monkeypatch.setattr(images, f'download_{kind}',
                            lambda appid, sgdb_id=None, game_name=None, _k=kind: fetched.append((_k, appid)) or 'steam')
    return written, fetched, fits


def test_a_first_match_refetches_covers_that_do_not_fit(lib):
    written, fetched, fits = lib
    metadata.write_backfill(-1, {'steam_appid': 620})
    assert fetched == [('vertical', -1), ('horizontal', -1)]
    assert (-1, {'vertical_art_source': 'steam'}) in written and (-1, {'horizontal_art_source': 'steam'}) in written


def test_a_cover_that_already_fits_is_left_alone(lib):
    written, fetched, fits = lib
    fits['vertical/-4'] = True                                   # Mixed: the store cover fits, the wide one does not
    metadata.write_backfill(-4, {'steam_appid': 620})
    assert fetched == [('horizontal', -4)]


def test_art_the_user_set_is_never_replaced(lib):
    written, fetched, fits = lib
    metadata.write_backfill(-2, {'steam_appid': 620})
    assert fetched == []


def test_only_the_first_match_triggers_it(lib):
    written, fetched, fits = lib
    metadata.write_backfill(-3, {'steam_appid': 556})            # already had a match
    assert fetched == []
    metadata.write_backfill(-1, {'developers': 'x'})              # a result without a match
    assert fetched == []


def test_steam_games_are_not_touched(lib):
    written, fetched, fits = lib
    metadata.write_backfill(10, {'steam_appid': 10})
    assert fetched == []


def test_a_failing_art_fetch_never_breaks_the_save(lib, monkeypatch):
    written, fetched, fits = lib
    monkeypatch.setattr(images, 'download_vertical', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')))
    metadata.write_backfill(-1, {'steam_appid': 620})
    assert (-1, {'steam_appid': 620}) in written
