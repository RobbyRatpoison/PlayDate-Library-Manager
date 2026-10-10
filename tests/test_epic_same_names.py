"""Epic can list a base game and a standalone expansion under one catalog title; the sync step
renames only the colliding rows, from the product's own store title. The Epic plugin is not part
of this repo's checkout (plugins/*/ is ignored), so this is skipped where it isn't installed."""
import importlib.util
import os
import sqlite3

import pytest

import database

EPIC = os.path.join(os.path.dirname(__file__), '..', 'plugins', 'epic_games', 'epic.py')
pytestmark = pytest.mark.skipif(not os.path.exists(EPIC), reason='Epic plugin not installed')


@pytest.fixture
def epic(tmp_path, monkeypatch):
    path = str(tmp_path / 'games.db')
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE games (appid INTEGER PRIMARY KEY, name TEXT, platform TEXT, platform_ns TEXT,
                    meta_backfill_fetched TEXT, steam_appid INTEGER)""")
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?)", [
        (-1, 'Shadow Tactics: Blades of the Shogun', 'epic_games', 'ns_base', '2026-10-08', 418240),
        (-2, 'Shadow Tactics Blades of the Shogun',  'epic_games', 'ns_aiko', '2026-10-08', 418240),
        (-3, 'Unrelated Game',                       'epic_games', 'ns_other', None, None),
        (-4, 'Shadow Tactics: Blades of the Shogun', 'gog',        None, None, None),
    ])
    conn.commit()
    conn.close()

    def open_conn():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c
    monkeypatch.setattr(database, '_db', lambda: path)
    monkeypatch.setattr(database, 'get_db', open_conn)
    spec = importlib.util.spec_from_file_location('epic_under_test', EPIC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._test_conn = open_conn
    return mod


def _names(mod):
    return {r['appid']: r['name'] for r in mod._test_conn().execute("SELECT appid, name FROM games")}


def _store(titles):
    return lambda query, variables: [{'title': titles[variables['namespace']], 'offerType': 'BASE_GAME',
                                      'namespace': variables['namespace']}]


def test_only_the_colliding_row_with_a_different_store_title_is_renamed(epic, monkeypatch):
    monkeypatch.setattr(epic, '_store_elements', _store({
        'ns_base': 'Shadow Tactics: Blades of the Shogun', 'ns_aiko': "Shadow Tactics - Aiko's Choice"}))
    assert epic._disambiguate_same_names() == 1
    names = _names(epic)
    assert names[-2] == "Shadow Tactics - Aiko's Choice"
    assert names[-1] == 'Shadow Tactics: Blades of the Shogun' and names[-3] == 'Unrelated Game'
    assert names[-4] == 'Shadow Tactics: Blades of the Shogun'          # another platform's row is never touched
    row = epic._test_conn().execute("SELECT meta_backfill_fetched, steam_appid FROM games WHERE appid=-2").fetchone()
    assert row['meta_backfill_fetched'] == '0' and row['steam_appid'] is None   # re-resolved under the new name
    assert epic._disambiguate_same_names() == 0                                 # nothing left to do


def test_a_store_title_that_does_not_help_changes_nothing(epic, monkeypatch):
    monkeypatch.setattr(epic, '_store_elements', _store({
        'ns_base': 'Shadow Tactics: Blades of the Shogun', 'ns_aiko': 'Shadow Tactics Blades of the Shogun'}))
    assert epic._disambiguate_same_names() == 0


def test_the_same_product_listed_twice_is_left_alone(epic, monkeypatch):
    conn = epic._test_conn()
    conn.execute("UPDATE games SET platform_ns = 'ns_base' WHERE appid = -2")
    conn.commit()
    monkeypatch.setattr(epic, '_store_elements', _store({'ns_base': 'Anything Else'}))
    assert epic._disambiguate_same_names() == 0
