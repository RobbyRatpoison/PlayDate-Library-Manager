"""Artwork: the right shape beats the source order (unless switched off). The runners are stubbed to
write images of chosen sizes at the game's file."""

import pytest
from PIL import Image

import images


@pytest.fixture
def art(tmp_path, monkeypatch):
    monkeypatch.setattr(images, 'VERTICAL_DIR', str(tmp_path))
    monkeypatch.setattr(images, 'HORIZONTAL_DIR', str(tmp_path))
    monkeypatch.setattr(images, 'ICONS_DIR', str(tmp_path))
    monkeypatch.setattr(images, '_ensure_dirs', lambda: None)
    monkeypatch.setattr(images, 'save_as_jpg', lambda content, path: open(path, 'wb').write(content) or True)
    return tmp_path


def _writer(path, sizes, log):
    """attempt(src): write the image `sizes[src]` at `path` (or fail) and return the source's tag."""
    def attempt(src):
        log.append(src)
        if sizes.get(src) is None:
            return 'missing'
        Image.new('RGB', sizes[src]).save(path, 'JPEG')
        return f'tag_{src}'
    return attempt


def _size_at(path):
    return Image.open(path).size


def test_the_first_source_wins_when_its_art_fits(art):
    path, log = images._art_path('vertical', 7), []
    out = images._download_preferring_fit('vertical', 7, ['steam', 'store', 'sgdb'],
                                          _writer(path, {'steam': (600, 900), 'store': (600, 900)}, log))
    assert out == 'tag_steam' and log == ['steam']                  # nothing else was fetched


def test_a_later_source_that_fits_beats_an_earlier_one_that_does_not(art):
    path, log = images._art_path('vertical', 7), []
    out = images._download_preferring_fit('vertical', 7, ['steam', 'store', 'sgdb'],
                                          _writer(path, {'steam': (1200, 1600), 'store': (900, 1350)}, log))
    assert out == 'tag_store' and log == ['steam', 'store'] and _size_at(path) == (900, 1350)


def test_with_nothing_fitting_the_first_result_is_kept(art):
    path, log = images._art_path('horizontal', 7), []
    out = images._download_preferring_fit('horizontal', 7, ['steam', 'store', 'sgdb'],
                                          _writer(path, {'steam': (500, 500), 'sgdb': (920, 430)}, log))
    assert out == 'tag_steam' and log == ['steam', 'store', 'sgdb'] and _size_at(path) == (500, 500)


def test_sources_that_have_nothing_are_skipped_and_all_missing_is_missing(art):
    path, log = images._art_path('vertical', 7), []
    assert images._download_preferring_fit('vertical', 7, ['steam', 'sgdb'], _writer(path, {'sgdb': (600, 900)}, log)) == 'tag_sgdb'
    assert images._download_preferring_fit('vertical', 8, ['steam', 'sgdb'], _writer(images._art_path('vertical', 8), {}, [])) == 'missing'


def test_the_fit_uses_the_cards_five_percent_tolerance(art):
    path = images._art_path('horizontal', 7)
    Image.new('RGB', (616, 353)).save(path, 'JPEG')
    assert images._art_fits(path, 'horizontal')
    Image.new('RGB', (920, 430)).save(path, 'JPEG')                 # SteamGridDB's wide art: 2.14
    assert not images._art_fits(path, 'horizontal')
    Image.new('RGB', (1920, 1080)).save(path, 'JPEG')               # 16:9 is within 2% of the card
    assert images._art_fits(path, 'horizontal')
    assert not images._art_fits(str(art / 'nope.jpg'), 'vertical')




@pytest.fixture
def pipeline(art, monkeypatch):
    """_download_art with the runners stubbed: Steam game 7, sources tagged by what they ran as."""
    import config
    state = {'art_prefer_fit': True}
    monkeypatch.setattr(config, 'load_state', lambda: state)
    sizes, log = {}, []

    def runner(kind):
        def run(appid, assets, src, sgdb_id, game_name):
            log.append(src)
            if sizes.get(src) is None:
                return 'missing'
            Image.new('RGB', sizes[src]).save(images._art_path(kind, appid), 'JPEG')
            return src
        return run
    monkeypatch.setattr(images, '_download_vertical', runner('vertical'))
    monkeypatch.setattr(images, '_download_horizontal', runner('horizontal'))
    return state, sizes, log


def test_the_default_for_a_steam_game_takes_steam_then_sgdb(pipeline):
    state, sizes, log = pipeline
    sizes.update(steam=(600, 900), sgdb=(600, 900))
    assert images.download_vertical(7) == 'steam' and log == ['steam']


def test_prefer_fit_takes_a_fitting_sgdb_image_over_a_wrong_steam_one(pipeline):
    state, sizes, log = pipeline
    sizes.update(steam=(460, 215), sgdb=(616, 353))
    assert images.download_horizontal(7) == 'sgdb' and log == ['steam', 'sgdb']


def test_switching_it_off_goes_back_to_plain_source_order(pipeline):
    state, sizes, log = pipeline
    state['art_prefer_fit'] = False
    sizes.update(steam=(460, 215), sgdb=(616, 353))
    assert images.download_horizontal(7) == 'steam' and log == ['steam']


def test_a_saved_order_is_still_the_order_the_shape_check_walks(pipeline):
    state, sizes, log = pipeline
    state['art_source_prefs'] = {'steam': {'vertical': ['sgdb', 'steam']}}
    sizes.update(steam=(600, 900), sgdb=(600, 900))
    assert images.download_vertical(7) == 'sgdb' and log == ['sgdb']
    state['art_source_prefs'] = {'steam': {'vertical': ['sgdb']}}                   # steam switched off
    sizes.update(sgdb=(1000, 1000))
    assert images.download_vertical(7) == 'sgdb'


def test_an_explicit_source_bypasses_all_of_it(pipeline):
    state, sizes, log = pipeline
    sizes.update(sgdb=(1000, 1000), steam=(600, 900))
    assert images.download_vertical(7, source='sgdb') == 'sgdb' and log == ['sgdb']
