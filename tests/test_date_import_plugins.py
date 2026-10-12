"""Purchase dates: how the bulk date import picks a source per plugin, and each store plugin's
single-game sync (the edit modal's sync button) saving the purchase date.

Plugin folders are gitignored (installed from their own repos), so the plugin tests skip when a
plugin isn't present; the core dispatch test always runs."""
import importlib
import os
import sqlite3
import time
import types

import pytest
from flask import Flask

import database
import date_import

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _need(plugin_id):
    if not os.path.isfile(os.path.join(ROOT, 'plugins', plugin_id, 'plugin.json')):
        pytest.skip(f'plugin {plugin_id} is not installed here')


@pytest.fixture
def lib_db(tmp_path, monkeypatch):
    """A throwaway games table; patches get_db/update_game_data everywhere they were imported."""
    path = str(tmp_path / 'games.db')
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE games (appid INTEGER PRIMARY KEY, name TEXT, platform TEXT, "
                 "platform_id TEXT, platform_slug TEXT, platform_ns TEXT, date_added INTEGER)")
    conn.commit()
    conn.close()

    def open_db():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c

    def update(appid, **kw):
        c = open_db()
        cols = {r[1] for r in c.execute("PRAGMA table_info(games)")}
        kw = {k: v for k, v in kw.items() if k in cols}     # the real table has many more columns
        if not kw:
            c.close()
            return
        c.execute(f"UPDATE games SET {', '.join(k + ' = ?' for k in kw)} WHERE appid = ?", [*kw.values(), appid])
        c.commit()
        c.close()

    monkeypatch.setattr(database, 'get_db', open_db)
    monkeypatch.setattr(database, 'update_game_data', update)
    monkeypatch.setattr(date_import, 'get_db', open_db)

    def patch_modules(*mods):
        for m in mods:
            if hasattr(m, 'get_db'):
                monkeypatch.setattr(m, 'get_db', open_db)
            if hasattr(m, 'update_game_data'):
                monkeypatch.setattr(m, 'update_game_data', update)

    def add(appid, name, platform, platform_id='', slug=''):
        c = open_db()
        c.execute("INSERT INTO games (appid, name, platform, platform_id, platform_slug) VALUES (?,?,?,?,?)",
                  (appid, name, platform, platform_id, slug))
        c.commit()
        c.close()

    def date_of(appid):
        c = open_db()
        v = c.execute("SELECT date_added FROM games WHERE appid = ?", (appid,)).fetchone()[0]
        c.close()
        return v

    return types.SimpleNamespace(add=add, date_of=date_of, patch=patch_modules, open=open_db)


# ── Core: which source the bulk import uses ────────────────────────────────────

def _run_bulk(monkeypatch, plugins_by_platform, appids):
    import plugins as plugins_pkg
    monkeypatch.setattr(plugins_pkg, 'get_for_platform', lambda plat: plugins_by_platform.get(plat))
    snapshot = dict(date_import._bulk_date_state)
    app = Flask(__name__)
    app.register_blueprint(date_import.date_import_bp)
    try:
        resp = app.test_client().post('/api/bulk-date-import/start', json={'appids': appids})
        deadline = time.time() + 5
        while date_import._bulk_date_state['api_threads_running'] > 0 and time.time() < deadline:
            time.sleep(0.02)
        return resp.get_json(), dict(date_import._bulk_date_state)
    finally:
        date_import._bulk_date_state.clear()
        date_import._bulk_date_state.update(snapshot)


class _Direct:                      # fetch_purchase_dates only
    name = 'Direct'
    def fetch_purchase_dates(self, appids, on_result):
        for a in appids:
            on_result(a, 1_600_000_000 if a == -1 else None)


class _UrlOnly:                     # userscript only
    name = 'UrlOnly'
    date_import_url = 'https://example.test/orders'


class _Both(_Direct):               # a date_import_url wins over fetch_purchase_dates
    name = 'Both'
    date_import_url = 'https://example.test/both'


def test_plugin_with_only_fetch_purchase_dates_is_fetched_directly(lib_db, monkeypatch):
    lib_db.add(-1, 'A', 'direct'); lib_db.add(-2, 'B', 'direct')
    out, state = _run_bulk(monkeypatch, {'direct': _Direct()}, [-1, -2])
    assert out['date_import_urls'] == [] and out['total'] == 2
    assert lib_db.date_of(-1) == 1_600_000_000 and lib_db.date_of(-2) is None
    assert (state['done'], state['failed']) == (1, 1)


def test_plugin_with_a_date_import_url_goes_to_the_userscript(lib_db, monkeypatch):
    lib_db.add(-1, 'A', 'urlonly')
    out, state = _run_bulk(monkeypatch, {'urlonly': _UrlOnly()}, [-1])
    assert [u['url'] for u in out['date_import_urls']] == ['https://example.test/orders']
    assert out['total'] == 0


def test_a_date_import_url_beats_fetch_purchase_dates(lib_db, monkeypatch):
    """The reason GOG and EA dropped their URL: with both, core never uses the direct import."""
    lib_db.add(-1, 'A', 'both')
    out, _ = _run_bulk(monkeypatch, {'both': _Both()}, [-1])
    assert out['date_import_urls'] and out['total'] == 0
    assert lib_db.date_of(-1) is None


# ── Plugins: no leftover userscript URL, a direct import instead ───────────────

@pytest.mark.parametrize('pid', ['gog', 'ea_app', 'ubisoft'])
def test_plugin_has_no_dead_userscript_url(pid):
    _need(pid)
    mod = importlib.import_module(f'plugins.{pid}')
    assert not hasattr(mod.plugin, 'date_import_url')


@pytest.mark.parametrize('pid', ['gog', 'ea_app', 'epic_games', 'humble', 'indiegala', 'itch_io'])
def test_plugin_fetches_dates_directly(pid):
    _need(pid)
    mod = importlib.import_module(f'plugins.{pid}')
    assert callable(getattr(mod.plugin, 'fetch_purchase_dates', None))
    assert not hasattr(mod.plugin, 'date_import_url')


def test_gog_import_button_has_a_single_definition_that_calls_the_api():
    _need('gog')
    path = os.path.join(ROOT, 'plugins', 'gog', 'templates', 'gog_tools_scripts.html')
    src = open(path, encoding='utf-8').read()
    assert src.count('function gogImportDates') == 1
    assert '/api/gog/import-purchase-dates' in src
    assert 'account/settings/orders' not in src


# ── GOG: matching and the bulk entry point ─────────────────────────────────────

@pytest.fixture
def gog_mod(lib_db, monkeypatch):
    _need('gog')
    from plugins.gog import gog
    lib_db.patch(gog)
    monkeypatch.setattr(gog, '_pack_contents', lambda pid: [])
    monkeypatch.setattr(gog.time, 'sleep', lambda s: None)
    return gog


def test_gog_reports_every_selected_game_and_never_writes(lib_db, gog_mod, monkeypatch):
    lib_db.add(-1, 'Alpha', 'gog', '1'); lib_db.add(-2, 'Beta', 'gog', '2')
    lib_db.add(-3, 'Gamma', 'gog', '3'); lib_db.add(-4, 'Delta Edition', 'gog', '4')
    monkeypatch.setattr(gog_mod, 'fetch_purchase_dates',
                        lambda: ({'1': 100, '9': 400}, {'1': 'Alpha', '9': 'Delta Edition'}))
    got = {}
    res = gog_mod.import_purchase_dates({'1', '2', '4'}, on_result=lambda a, t: got.__setitem__(a, t))
    assert got == {-1: 100, -2: None, -4: 400}          # -4 matched by title; -3 not selected
    assert res['updated'] == 2 and res['by_title'] == 1 and res['no_date'] == ['Beta']
    assert all(lib_db.date_of(a) is None for a in (-1, -2, -3, -4))


def test_gog_pack_orders_give_their_games_the_pack_date(lib_db, gog_mod, monkeypatch):
    lib_db.add(-1, 'In A Pack', 'gog', '5')
    monkeypatch.setattr(gog_mod, 'fetch_purchase_dates', lambda: ({'77': 700}, {'77': 'Big Pack'}))
    monkeypatch.setattr(gog_mod, '_pack_contents', lambda pid: ['5'] if pid == '77' else [])
    got = {}
    gog_mod.import_purchase_dates({'5'}, on_result=lambda a, t: got.__setitem__(a, t))
    assert got == {-1: 700}


def test_gog_without_on_result_still_writes_the_date(lib_db, gog_mod, monkeypatch):
    lib_db.add(-1, 'Alpha', 'gog', '1')
    monkeypatch.setattr(gog_mod, 'fetch_purchase_dates', lambda: ({'1': 100}, {'1': 'Alpha'}))
    gog_mod.import_purchase_dates({'1'})
    assert lib_db.date_of(-1) == 100


def test_gog_plugin_fetch_purchase_dates_reports_and_errors_when_logged_out(lib_db, gog_mod, monkeypatch):
    from plugins.gog import plugin
    lib_db.add(-1, 'Alpha', 'gog', '1')
    monkeypatch.setattr(gog_mod, 'fetch_purchase_dates', lambda: ({'1': 100}, {'1': 'Alpha'}))
    got = {}
    plugin.fetch_purchase_dates([-1], lambda a, t: got.__setitem__(a, t))
    assert got == {-1: 100}
    monkeypatch.setattr(gog_mod, 'fetch_purchase_dates', lambda: None)
    with pytest.raises(RuntimeError):
        plugin.fetch_purchase_dates([-1], lambda a, t: None)


# ── EA: same, with the entitlement list ────────────────────────────────────────

@pytest.fixture
def ea_mod(lib_db, monkeypatch):
    _need('ea_app')
    from plugins.ea_app import ea
    lib_db.patch(ea)
    monkeypatch.setattr(ea, 'get_valid_session', lambda: object())
    monkeypatch.setattr(ea, '_get_pid', lambda: 1)
    monkeypatch.setattr(ea, '_fetch_entitlement_dates', lambda s, p: {'o1': 100, 'o3': 300})
    return ea


def test_ea_reports_selected_games_only_and_never_writes(lib_db, ea_mod):
    for a, o in ((-1, 'o1'), (-2, 'o2'), (-3, 'o3')):
        lib_db.add(a, f'G{a}', 'ea_app', o)
    got = {}
    res = ea_mod.import_purchase_dates({'o1', 'o2'}, on_result=lambda a, t: got.__setitem__(a, t))
    assert got == {-1: 100, -2: None} and res == {'updated': 1, 'missing': 1}
    assert lib_db.date_of(-1) is None


def test_ea_plugin_fetch_purchase_dates_errors_when_the_request_fails(lib_db, ea_mod, monkeypatch):
    from plugins.ea_app import plugin
    lib_db.add(-1, 'G', 'ea_app', 'o1')
    monkeypatch.setattr(ea_mod, '_fetch_entitlement_dates', lambda s, p: {})
    with pytest.raises(RuntimeError):
        plugin.fetch_purchase_dates([-1], lambda a, t: None)


# ── Single-game sync (the edit modal's button) per plugin ──────────────────────

TS = 1_600_000_000          # 2020-09-13
META = {'name': 'Synced Name'}


def _gog(monkeypatch, lib_db, ts):
    from plugins.gog import gog, routes
    lib_db.patch(routes)
    monkeypatch.setattr(gog, 'fetch_gog_metadata', lambda gid: dict(META))
    monkeypatch.setattr(gog, 'fetch_gog_achievements', lambda *a: None)
    monkeypatch.setattr(gog, 'get_valid_session', lambda: None)
    monkeypatch.setattr(gog, 'get_galaxy_user_id', lambda: None)
    lib_db.patch(gog)
    monkeypatch.setattr(gog, 'fetch_purchase_dates', lambda: (({'1': ts}, {'1': 'G'}) if ts else None))
    return routes


def _ea(monkeypatch, lib_db, ts):
    from plugins.ea_app import ea, routes
    lib_db.patch(routes, ea)
    monkeypatch.setattr(ea, 'scrape_single', lambda appid: dict(META))
    monkeypatch.setattr(ea, 'get_valid_session', lambda: object())
    monkeypatch.setattr(ea, '_get_pid', lambda: 1)
    monkeypatch.setattr(ea, '_fetch_entitlement_dates', lambda s, p: ({'1': ts} if ts else {}))
    return routes


def _epic(monkeypatch, lib_db, ts):
    from plugins.epic_games import epic, routes
    lib_db.patch(routes, epic)
    monkeypatch.setattr(epic, 'scrape_single', lambda appid: dict(META))
    monkeypatch.setattr(epic, '_fetch_entitlement_date_maps', lambda: ({}, ({'1': ts} if ts else {})))
    return routes


def _humble(monkeypatch, lib_db, ts):
    from plugins.humble import humble, routes
    lib_db.patch(routes, humble)
    monkeypatch.setattr(humble, 'rescrape', lambda appid: dict(META))
    monkeypatch.setattr(humble, 'fetch_dates_for_appids',
                        lambda appids, cb: [cb(a, ts) for a in appids])
    return routes


def _indiegala(monkeypatch, lib_db, ts):
    from plugins.indiegala import indiegala, routes
    lib_db.patch(routes, indiegala)
    monkeypatch.setattr(indiegala, 'is_connected', lambda: True)
    monkeypatch.setattr(indiegala, 'rescrape', lambda appid: dict(META))
    monkeypatch.setattr(indiegala, 'fetch_dates_for_appids', lambda appids: {a: ts for a in appids})
    return routes


def _itch(monkeypatch, lib_db, ts):
    from plugins.itch_io import itch_io, routes
    lib_db.patch(routes, itch_io)
    monkeypatch.setattr(itch_io, 'rescrape_game', lambda appid: dict(META))
    monkeypatch.setattr(itch_io, 'fetch_dates_for_appids',
                        lambda appids, cb: [cb(a, ts) for a in appids])
    return routes


SYNC = [('gog', 'gog', _gog), ('ea_app', 'ea_app', _ea), ('epic_games', 'epic_games', _epic),
        ('humble', 'humble', _humble), ('indiegala', 'indiegala', _indiegala), ('itch_io', 'itch_io', _itch)]


def _client(routes_mod):
    from werkzeug.routing import IntegerConverter

    class SignedIntConverter(IntegerConverter):             # as create_app() does: other stores' appids are negative
        regex = r'-?\d+'
        num_convert = int

    app = Flask(__name__)
    app.url_map.converters['int'] = SignedIntConverter
    app.register_blueprint(routes_mod.bp)
    return app.test_client()


@pytest.mark.parametrize('pid,platform,setup', SYNC, ids=[s[0] for s in SYNC])
def test_single_game_sync_saves_and_returns_the_purchase_date(pid, platform, setup, lib_db, monkeypatch):
    _need(pid)
    lib_db.add(-1, 'Old Name', platform, '1', 'slug')
    routes = setup(monkeypatch, lib_db, TS)
    resp = _client(routes).post(f'/api/{pid}/scrape-single/-1')
    body = resp.get_json()
    assert resp.status_code == 200 and body['status'] == 'success', body
    assert body['data']['date_added'] == '2020-09-13'          # the edit modal's Date Added box shows this
    assert lib_db.date_of(-1) == TS
    c = lib_db.open()
    assert c.execute("SELECT name FROM games WHERE appid = -1").fetchone()[0] == 'Synced Name'
    c.close()


@pytest.mark.parametrize('pid,platform,setup', SYNC, ids=[s[0] for s in SYNC])
def test_single_game_sync_survives_a_missing_purchase_date(pid, platform, setup, lib_db, monkeypatch):
    _need(pid)
    lib_db.add(-1, 'Old Name', platform, '1', 'slug')
    routes = setup(monkeypatch, lib_db, None)
    resp = _client(routes).post(f'/api/{pid}/scrape-single/-1')
    body = resp.get_json()
    assert resp.status_code == 200 and body['status'] == 'success', body
    assert 'date_added' not in body['data']
    assert lib_db.date_of(-1) is None                          # nothing found: the stored date is left alone
    c = lib_db.open()
    assert c.execute("SELECT name FROM games WHERE appid = -1").fetchone()[0] == 'Synced Name'
    c.close()


@pytest.mark.parametrize('pid,platform,setup', SYNC, ids=[s[0] for s in SYNC])
def test_single_game_sync_survives_a_date_lookup_that_raises(pid, platform, setup, lib_db, monkeypatch):
    _need(pid)
    lib_db.add(-1, 'Old Name', platform, '1', 'slug')
    routes = setup(monkeypatch, lib_db, TS)
    boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('lookup failed'))
    target = {'gog': 'plugins.gog.gog.fetch_purchase_dates', 'ea_app': 'plugins.ea_app.ea._fetch_entitlement_dates',
              'epic_games': 'plugins.epic_games.epic._fetch_entitlement_date_maps',
              'humble': 'plugins.humble.humble.fetch_dates_for_appids',
              'indiegala': 'plugins.indiegala.indiegala.fetch_dates_for_appids',
              'itch_io': 'plugins.itch_io.itch_io.fetch_dates_for_appids'}[pid]
    monkeypatch.setattr(target, boom)
    resp = _client(routes).post(f'/api/{pid}/scrape-single/-1')
    body = resp.get_json()
    assert resp.status_code == 200 and body['status'] == 'success', body
    assert lib_db.date_of(-1) is None


def test_edit_modal_refreshes_date_added_after_a_plugin_sync():
    """Without this the stale Date Added box would overwrite the new date on Save."""
    src = open(os.path.join(ROOT, 'templates', 'modal_edit.html'), encoding='utf-8').read()
    body = src[src.index('async function fetchMetadata()'):]
    body = body[:body.index('async function', 10)] if 'async function' in body[10:] else body
    assert "safeSet('edit-date-added', game.date_added)" in body


# ── Platforms with no date source ──────────────────────────────────────────────

class _NoSource:
    name = 'NoSource'


def test_start_reports_games_no_plugin_can_supply_dates_for(lib_db, monkeypatch):
    lib_db.add(-1, 'A', 'direct'); lib_db.add(-2, 'B', 'nosource'); lib_db.add(-3, 'C', 'nosource')
    lib_db.add(-4, 'D', 'custom')                                  # a platform with no plugin at all
    out, state = _run_bulk(monkeypatch, {'direct': _Direct(), 'nosource': _NoSource()}, [-1, -2, -3, -4])
    assert out['unsupported'] == {'nosource': 2, 'custom': 1}
    assert out['total'] == 1                                        # only the direct game is queued


def test_start_with_only_unsupported_games_queues_nothing(lib_db, monkeypatch):
    lib_db.add(-2, 'B', 'nosource')
    out, _ = _run_bulk(monkeypatch, {'nosource': _NoSource()}, [-2])
    assert out['total'] == 0 and out['date_import_urls'] == [] and out['unsupported'] == {'nosource': 1}


def test_plugin_js_api_says_where_each_platforms_dates_come_from(monkeypatch):
    import plugins as plugins_pkg

    def fake(platform, base):
        return type('P', (base,), {'platform': platform, 'name': platform, 'js_api': lambda self: {}})()
    monkeypatch.setattr(plugins_pkg, '_plugins', {
        'u': fake('u', _UrlOnly), 'a': fake('a', _Direct), 'n': fake('n', _NoSource)})
    api = plugins_pkg.plugin_js_api()
    assert (api['u']['date_import'], api['a']['date_import'], api['n']['date_import']) == ('userscript', 'api', None)
