"""saved_filter_ref nodes: a filter tree that includes other saved filters."""
import sqlite3

import config
from library import build_tree_sql, saved_filter_would_cycle


def _cond(col, op, val):
    return {'type': 'condition', 'column': col, 'operator': op, 'value': val}


def _state(monkeypatch, saved):
    monkeypatch.setattr(config, 'load_state', lambda: {'saved_filters': saved})


def _run(tree):
    params = []
    sql = build_tree_sql(tree, params)
    db = sqlite3.connect(':memory:')
    db.execute("CREATE TABLE games (appid INTEGER, installed INTEGER, tags TEXT, groups TEXT)")
    db.executemany("INSERT INTO games VALUES (?,?,?,?)", [
        (1, 1, '', ''),          # installed only
        (2, 0, 'A', 'G'),        # both filters
        (3, 0, 'A', ''),         # only filter A
        (4, 0, '', 'G'),         # only filter B
        (5, 0, '', ''),          # nothing
    ])
    return sorted(r[0] for r in db.execute(f"SELECT appid FROM games WHERE {sql}", params))


def _saved():
    return {
        'FA': {'id': 'ida', 'tree': {'type': 'group', 'logic': 'AND', 'items': [_cond('tags', 'LIKE', 'A')]}},
        'FB': {'id': 'idb', 'tree': {'type': 'group', 'logic': 'AND', 'items': [_cond('groups', 'LIKE', 'G')]}},
    }


def _ref(fid, name='', **kw):
    return {'type': 'saved_filter_ref', 'id': fid, 'name': name, **kw}


def test_installed_or_both_filters(monkeypatch):
    _state(monkeypatch, _saved())
    tree = {'type': 'group', 'logic': 'OR', 'items': [
        _cond('installed', '=', '1'),
        {'type': 'group', 'logic': 'AND', 'items': [_ref('ida'), _ref('idb')]},
    ]}
    assert _run(tree) == [1, 2]


def test_negate(monkeypatch):
    _state(monkeypatch, _saved())
    assert _run({'type': 'group', 'logic': 'AND', 'items': [_ref('ida', negate=True)]}) == [1, 4, 5]


def test_lookup_survives_rename_and_missing_matches_nothing(monkeypatch):
    saved = _saved()
    saved['Renamed'] = saved.pop('FA')
    _state(monkeypatch, saved)
    assert _run(_ref('ida', 'FA')) == [2, 3]
    assert _run(_ref('gone', 'Deleted')) == []


def test_cycle_matches_nothing_and_is_detected(monkeypatch):
    saved = _saved()
    saved['FA']['tree'] = {'type': 'group', 'logic': 'AND', 'items': [_ref('idb')]}
    saved['FB']['tree'] = {'type': 'group', 'logic': 'AND', 'items': [_ref('ida')]}
    _state(monkeypatch, saved)
    assert _run(_ref('ida')) == []
    assert saved_filter_would_cycle(_saved(), {'type': 'group', 'items': [_ref('ida')]}, 'ida', 'FA')
    assert not saved_filter_would_cycle(_saved(), {'type': 'group', 'items': [_ref('ida')]}, 'idc', 'FC')
