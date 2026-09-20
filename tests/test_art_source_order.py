"""images.art_source_order: which sources to try, in what order, for one art type on
one platform (user's Artwork Sources setting + whether the plugin offers store art)."""
from images import art_source_order


def test_untouched_platform_without_store_art_runs_the_original_chain():
    assert art_source_order('vertical', 'steam', False, None) is None
    assert art_source_order('vertical', 'gog', False, None) is None


def test_untouched_platform_with_store_art_defaults_to_store_sgdb_steam():
    assert art_source_order('vertical', 'epic_games', True, None) == ['store', 'sgdb', 'steam']


def test_saved_order_is_honoured_exactly():
    assert art_source_order('vertical', 'epic_games', True, ['sgdb', 'store']) == ['sgdb', 'store']
    assert art_source_order('icon', 'gog', False, ['steam', 'sgdb']) == ['steam', 'sgdb']


def test_switched_off_sources_are_never_added_back():
    assert art_source_order('horizontal', 'epic_games', True, ['store']) == ['store']
    assert art_source_order('horizontal', 'epic_games', True, []) == []


def test_store_is_dropped_when_the_plugin_has_no_art_urls():
    assert art_source_order('vertical', 'gog', False, ['store', 'sgdb']) == ['sgdb']


def test_unknown_source_names_are_ignored():
    assert art_source_order('vertical', 'steam', False, ['bogus', 'steam']) == ['steam']
