"""The backfill's last tier (a platform's own store page) fills developer and publisher as well as
genres, categories, tags and release date, and only into fields that are still empty."""
import sqlite3

import pytest

import metadata

COLS = ("appid INTEGER PRIMARY KEY, name TEXT, platform TEXT, platform_id TEXT, platform_slug TEXT, "
        "steam_appid INTEGER, meta_backfill_fetched TEXT, developers TEXT, publishers TEXT, genres TEXT, "
        "categories TEXT, tags TEXT, release_date INTEGER, review_score TEXT, is_free INTEGER, "
        "metacritic_score INTEGER, short_description TEXT, total_achievements INTEGER")


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / 'games.db')
    c = sqlite3.connect(path)
    c.execute(f"CREATE TABLE games ({COLS})")
    c.commit()
    c.close()

    def open_db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr(metadata, 'get_db', open_db)
    # No Steam or PCGamingWiki match, and no plugin description: only the store page can answer.
    monkeypatch.setattr(metadata, '_resolve', lambda name: (None, 'none', None))
    monkeypatch.setattr(metadata, '_plugin_description', lambda *a, **k: None)
    return open_db


def _add(db, **row):
    c = db()
    c.execute("INSERT INTO games (appid, name, platform, platform_slug, meta_backfill_fetched, developers, publishers) "
              "VALUES (?, ?, 'nintendo', ?, ?, ?, ?)",
              (-5, 'Golf Story', row.get('slug', '/us/store/products/golf-story-switch/'), row.get('stamp', '0'),
               row.get('developers'), row.get('publishers')))
    c.commit()
    c.close()


PAGE = {'genres': 'Role playing,Sports', 'developers': 'Sidebar Games', 'publishers': 'Sidebar Games',
        'release_date': 1506556800}


def test_store_page_fills_developer_and_publisher(db, monkeypatch):
    _add(db)
    monkeypatch.setattr(metadata, '_store_page_metadata', lambda platform, slug: PAGE)
    out = metadata.backfill_metadata(-5)
    assert out['developers'] == 'Sidebar Games' and out['publishers'] == 'Sidebar Games'
    assert out['genres'] == 'Role playing,Sports' and out['release_date'] == 1506556800


def test_store_page_never_overwrites_what_is_already_set(db, monkeypatch):
    _add(db, developers='My Edit', publishers='Kept')
    monkeypatch.setattr(metadata, '_store_page_metadata', lambda platform, slug: PAGE)
    out = metadata.backfill_metadata(-5)
    assert 'developers' not in out and 'publishers' not in out
    assert out['genres'] == 'Role playing,Sports'


def test_game_with_no_store_page_is_still_no_match(db, monkeypatch):
    _add(db, slug='')
    monkeypatch.setattr(metadata, '_store_page_metadata', lambda platform, slug: {} if not slug else PAGE)
    assert metadata.backfill_metadata(-5)['meta_backfill_fetched'] == 'no_match'
