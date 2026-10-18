from notifications import _applies_to_platform


def test_missing_or_blank_list_applies_everywhere():
    for n in ({}, {'platforms': []}, {'platforms': None}, {'platforms': ['', ' ']}, {'platforms': 'windows'}):
        for key in ('windows', 'linux', 'mac'):
            assert _applies_to_platform(n, key)


def test_listed_platforms_only():
    n = {'platforms': ['Windows', 'mac']}
    assert _applies_to_platform(n, 'windows')
    assert _applies_to_platform(n, 'mac')
    assert not _applies_to_platform(n, 'linux')
