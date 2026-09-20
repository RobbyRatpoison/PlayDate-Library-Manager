"""scrapers.clean_description: store blurb -> plain text shared by the Steam scrape
and the on-demand /api/game-description route."""
from scrapers import clean_description


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
