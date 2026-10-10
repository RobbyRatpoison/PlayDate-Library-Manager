from index import _clean_timing


def test_numbers_and_short_strings_pass_through():
    assert _clean_timing({'dcl': 120, 'fp': 12.5, 'env': {'gpu': 'NVIDIA'}}) == {'dcl': 120, 'fp': 12.5, 'env': {'gpu': 'NVIDIA'}}


def test_long_strings_are_cut_and_non_scalars_dropped():
    out = _clean_timing({'ua': 'x' * 500, 'bad': [1, 2], 'worse': object()})
    assert len(out['ua']) == 160 and out['bad'] is None and out['worse'] is None


def test_nesting_and_size_are_bounded():
    deep = {'a': {'b': {'c': {'d': 1}}}}
    assert _clean_timing(deep) == {'a': {'b': None}}
    assert len(_clean_timing({str(i): i for i in range(100)})) == 24


def test_booleans_become_numbers():
    assert _clean_timing({'x': True}) == {'x': 1}
