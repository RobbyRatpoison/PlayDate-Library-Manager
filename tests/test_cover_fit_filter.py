"""The 'Cover Shape' filter: follows the saved view (vertical covers unless horizontal view) and
selects by the edge data compute_art_edges stores."""
import sqlite3

import pytest

import config
import library


@pytest.fixture
def orientation(monkeypatch):
    state = {'artwork_orientation': 'vertical'}
    monkeypatch.setattr(config, 'load_state', lambda: state)
    return state


def _sql(value, op='='):
    params = []
    return library.build_tree_sql({'type': 'condition', 'column': 'cover_fit', 'operator': op, 'value': value}, params)


def test_vertical_view_reads_the_vertical_column(orientation):
    assert 'edge_vertical' in _sql('wrong') and 'edge_horizontal' not in _sql('wrong')


def test_horizontal_view_reads_the_horizontal_column(orientation):
    orientation['artwork_orientation'] = 'horizontal'
    assert 'edge_horizontal' in _sql('wrong') and 'edge_vertical' not in _sql('wrong')


def test_list_view_counts_as_vertical(orientation):
    orientation['artwork_orientation'] = 'list'
    assert 'edge_vertical' in _sql('fits')


def test_unknown_value_or_operator_filters_nothing(orientation):
    assert _sql('bogus') == '1=1'
    assert _sql('wrong', op='LIKE') == '1=1'


def test_selects_the_right_games_in_each_view(orientation):
    c = sqlite3.connect(':memory:')
    c.execute("CREATE TABLE games (appid INTEGER, edge_vertical TEXT, edge_horizontal TEXT)")
    c.executemany("INSERT INTO games VALUES (?,?,?)", [
        (1, '-', 'y#aaaaaa/#bbbbbb'),        # fits vertical, wrong horizontal
        (2, 'x#aaaaaa/#bbbbbb', '-'),        # wrong vertical, fits horizontal
        (3, None, None),                     # no cover
    ])

    def ids(value, op='='):
        return sorted(r[0] for r in c.execute(f"SELECT appid FROM games WHERE {_sql(value, op)}"))

    assert ids('wrong') == [2] and ids('fits') == [1] and ids('none') == [3]
    assert ids('wrong', '!=') == [1, 3] and ids('fits', '!=') == [2, 3]
    orientation['artwork_orientation'] = 'horizontal'
    assert ids('wrong') == [1] and ids('fits') == [2] and ids('none') == [3]
