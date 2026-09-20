"""scrapers.clean_description: store blurb -> plain text shared by the Steam scrape
and the on-demand /api/game-description route; description_lookup_due: the retry
window for lookups that found nothing."""
from datetime import date

from scrapers import clean_description, description_lookup_due


def test_empty_values_become_empty_string():
    assert clean_description(None) == ''
    assert clean_description('') == ''
    assert clean_description('   \n ') == ''


def test_decodes_entities():
    assert clean_description('Tom &amp; Jerry &quot;live&quot;') == 'Tom & Jerry "live"'


def test_strips_tags_without_gluing_words():
    assert clean_description('A<br>B <b>bold</b> text') == 'A B bold text'


def test_collapses_spaces_but_keeps_paragraph_breaks():
    assert clean_description('one   two\n\n\n\nthree') == 'one two\n\nthree'


TODAY = date(2026, 9, 20)


def test_never_checked_is_due():
    assert description_lookup_due(None, TODAY)
    assert description_lookup_due('', TODAY)


def test_recent_check_is_not_due_and_old_check_is():
    assert not description_lookup_due('2026-09-10', TODAY)          # 10 days ago
    assert not description_lookup_due('2026-09-07', TODAY)          # 13 days ago
    assert description_lookup_due('2026-09-06', TODAY)              # exactly 14 days
    assert description_lookup_due('2026-01-01', TODAY)


def test_unparseable_marker_is_due():
    assert description_lookup_due('not a date', TODAY)
