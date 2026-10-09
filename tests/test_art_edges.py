"""Edge colours for covers that don't fit their card (images.compute_art_edges)."""
from PIL import Image

import images
from images import compute_art_edges, EDGE_STOPS


def solid(w, h, rgb):
    return Image.new('RGB', (w, h), rgb)


def parse(value):
    d, rest = value[0], value[1:]
    a, b = rest.split('/')
    return d, a.split(','), b.split(',')


def test_cover_that_fits_needs_nothing():
    assert compute_art_edges(solid(600, 900, (10, 20, 30)), 'vertical') == '-'
    assert compute_art_edges(solid(616, 353, (10, 20, 30)), 'horizontal') == '-'
    assert compute_art_edges(solid(620, 900, (1, 2, 3)), 'vertical') == '-'     # 3% off: inside the tolerance
    assert compute_art_edges(solid(640, 900, (1, 2, 3)), 'vertical') != '-'     # 7% off: outside it


def test_wide_cover_gets_top_and_bottom_colours_darkened():
    img = solid(460, 215, (0, 0, 0))                     # a 2.14 header on the 1.75 card
    img.paste((200, 100, 50), (0, 0, 460, 20))           # top edge
    img.paste((0, 100, 200), (0, 195, 460, 215))         # bottom edge
    d, top, bottom = parse(compute_art_edges(img, 'horizontal'))
    assert d == 'y'
    assert len(top) == len(bottom) == EDGE_STOPS
    assert top[0] == '%02x%02x%02x' % (int(200 * 0.7), int(100 * 0.7), int(50 * 0.7))
    assert bottom[-1] == '%02x%02x%02x' % (0, int(100 * 0.7), int(200 * 0.7))


def test_tall_cover_gets_left_and_right_colours():
    img = solid(300, 900, (0, 0, 0))                     # taller than 2:3
    img.paste((255, 0, 0), (0, 0, 30, 900))
    img.paste((0, 0, 255), (270, 0, 300, 900))
    d, left, right = parse(compute_art_edges(img, 'vertical'))
    assert d == 'x'
    assert left[0] == 'b20000' and right[0] == '0000b2'


def test_colours_follow_the_edge():
    img = solid(1000, 300, (0, 0, 0))                    # wide for a vertical card
    img.paste((255, 255, 255), (0, 0, 500, 40))          # left half of the top edge is white
    _, top, _ = parse(compute_art_edges(img, 'vertical'))
    assert top[0] == 'b2b2b2' and top[-1] == '000000'


def test_unknown_kind_and_junk_give_none():
    assert compute_art_edges(solid(10, 10, (0, 0, 0)), 'icons') is None
    assert compute_art_edges(solid(1, 1, (0, 0, 0)), 'vertical') is None
    assert compute_art_edges(object(), 'vertical') is None


def test_art_path_is_parsed_for_both_slash_styles():
    m = images._ART_PATH_RE.search('/data/static/img/library/vertical/-123.jpg')
    assert m.groups() == ('vertical', '-123')
    m = images._ART_PATH_RE.search(r'C:\Play\static\img\library\horizontal\570.jpg')
    assert m.groups() == ('horizontal', '570')
    assert images._ART_PATH_RE.search('/data/static/img/library/icons/570.jpg') is None
