import json

from library import columnar_games


def _rebuild(cols, rows):
    return [dict(zip(cols, r)) for r in rows]


def test_rows_rebuild_the_games_with_the_key_order_tojson_used():
    games = [{'name': 'A', 'appid': 1, 'tags': 'x,y', 'hltb_main': None},
             {'name': 'B', 'appid': -2, 'tags': '', 'hltb_main': 90}]
    cols, rows = columnar_games(games)
    assert cols == ['appid', 'hltb_main', 'name', 'tags']                       # sorted
    rebuilt = _rebuild(cols, rows)
    assert rebuilt == games
    assert json.dumps(rebuilt) == json.dumps(games, sort_keys=True)            # byte-for-byte what tojson gave


def test_none_and_zero_values_survive():
    cols, rows = columnar_games([{'a': None, 'b': 0, 'c': '', 'd': [], 'e': False}])
    assert rows == [[None, 0, '', [], False]]


def test_games_whose_dicts_are_ordered_differently_still_work():
    games = [{'a': 1, 'b': 2}, {'b': 4, 'a': 3}]
    cols, rows = columnar_games(games)
    assert _rebuild(cols, rows) == games


def test_falls_back_when_the_keys_differ():
    assert columnar_games([{'a': 1, 'b': 2}, {'a': 1}]) is None
    assert columnar_games([{'a': 1}, {'a': 1, 'b': 2}]) is None


def test_empty_list_has_no_columnar_form():
    assert columnar_games([]) is None
