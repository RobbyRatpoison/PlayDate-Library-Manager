"""'From Steam' art: which Steam game a non-Steam game may borrow art from, and which Steam
URLs are tried for each kind."""
import sqlite3

import pytest

import database
import images


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / 'games.db')
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE games (appid INTEGER PRIMARY KEY, name TEXT, platform TEXT,
                    duplicate_of TEXT, steam_appid INTEGER, icon_hash TEXT)""")
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?)", [
        (620,  'Portal 2',          'steam',      None, None, 'abc123'),
        (-1,   'Portal 2',          'epic_games', '620', None, None),     # hidden duplicate of the Steam copy
        (-2,   'Linked by backfill', 'gog',       None, 620, None),       # resolved Steam match, no duplicate link
        (-3,   'Match not owned',   'gog',        None, 999999, None),    # resolved to a Steam game the library lacks
        (-4,   'No Steam copy',     'gog',        None, None, None),
    ])
    conn.commit()
    conn.close()

    def open_conn():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c
    monkeypatch.setattr(database, 'get_db', open_conn)
    return path


def test_duplicate_link_gives_the_steam_game_with_its_name_and_icon(db):
    assert images.steam_copy_of(-1) == {'steam_appid': 620, 'name': 'Portal 2', 'icon_hash': 'abc123'}


def test_backfill_match_is_used_when_there_is_no_duplicate_link(db):
    assert images.steam_copy_of(-2)['steam_appid'] == 620


def test_a_match_to_a_game_not_in_the_library_has_no_name(db):
    assert images.steam_copy_of(-3) == {'steam_appid': 999999, 'name': None, 'icon_hash': ''}


def test_no_copy_and_steam_games_themselves_give_none(db):
    assert images.steam_copy_of(-4) is None
    assert images.steam_copy_of(620) is None
    assert images.steam_copy_of(-12345) is None


class _Resp:
    def __init__(self, ok=True):
        self.status_code = 200 if ok else 404
        self.content = b'img'


def _run(monkeypatch, tmp_path, kind, assets, icon_hash='', failing=()):
    tried = []
    monkeypatch.setattr(images, '_get_steam_assets', lambda a: assets)
    monkeypatch.setattr(images, '_ensure_dirs', lambda: None)
    monkeypatch.setattr(images, 'VERTICAL_DIR', str(tmp_path))
    monkeypatch.setattr(images, 'HORIZONTAL_DIR', str(tmp_path))
    monkeypatch.setattr(images, 'ICONS_DIR', str(tmp_path))

    def fake_get(url, timeout=0):
        tried.append(url)
        return _Resp(not any(f in url for f in failing))
    monkeypatch.setattr(images.requests, 'get', fake_get)
    saved = []
    monkeypatch.setattr(images, 'save_as_jpg', lambda content, path: saved.append(path) or True)
    return images.download_from_steam(-1, 620, kind, icon_hash), tried, saved


def test_vertical_takes_the_2x_capsule_first_and_saves_under_the_games_own_id(monkeypatch, tmp_path):
    src, tried, saved = _run(monkeypatch, tmp_path, 'vertical', {'library_capsule_2x': 'http://x/2x.jpg', 'library_capsule': 'http://x/1x.jpg'})
    assert src == 'steam' and tried == ['http://x/2x.jpg'] and saved[0].endswith('-1.jpg')


def test_vertical_falls_back_to_the_legacy_cdn(monkeypatch, tmp_path):
    src, tried, _ = _run(monkeypatch, tmp_path, 'vertical', {}, failing=('2x',))
    base = 'https://cdn.cloudflare.steamstatic.com/steam/apps/620'
    assert src == 'steam' and tried == [f'{base}/library_600x900_2x.jpg', f'{base}/library_600x900.jpg']


def test_horizontal_prefers_the_manifest_header_then_header_jpg(monkeypatch, tmp_path):
    src, tried, _ = _run(monkeypatch, tmp_path, 'horizontal', {'header_image': 'http://x/h.jpg'}, failing=('x/h.jpg',))
    assert src == 'steam' and tried == ['http://x/h.jpg', 'https://cdn.cloudflare.steamstatic.com/steam/apps/620/header.jpg']


def test_icon_needs_the_steam_games_icon_hash(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, 'icon', {}, icon_hash='')[0] == 'missing'
    src, tried, _ = _run(monkeypatch, tmp_path, 'icon', {}, icon_hash='abc123')
    assert src == 'steam' and '/620/abc123_2x.jpg' in tried[0]


def test_everything_failing_reports_missing(monkeypatch, tmp_path):
    src, _, _ = _run(monkeypatch, tmp_path, 'horizontal', {}, failing=('steamstatic',))
    assert src == 'missing'
