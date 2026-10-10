"""crop_to_ratio: the kept area always has the card's exact ratio and stays inside the image."""
import pytest
from PIL import Image

import images


def _img(w, h):
    return Image.new('RGB', (w, h))


def _ratio(im):
    return im.size[0] / im.size[1]


def test_wider_than_two_thirds_crops_the_sides_to_exactly_two_thirds():
    out = images.crop_to_ratio(_img(660, 930), 0.0, 0.0, 620 / 660, 'vertical')
    assert out.size == (620, 930)


def test_the_frame_position_decides_which_part_is_kept():
    im = Image.new('RGB', (300, 200))
    for x in range(300):
        for y in range(200):
            im.putpixel((x, y), (x * 255 // 299, 0, 0))
    left  = images.crop_to_ratio(im, 0.0, 0.0, 0.5, 'icon')
    right = images.crop_to_ratio(im, 1.0, 0.0, 0.5, 'icon')
    assert left.getpixel((0, 0))[0] < right.getpixel((0, 0))[0]
    assert left.size == right.size == (150, 150)


def test_a_box_sticking_out_is_moved_back_inside():
    out = images.crop_to_ratio(_img(400, 600), 0.9, 0.9, 0.5, 'vertical')
    assert out.size == (200, 300)


def test_a_taller_than_ratio_image_crops_top_and_bottom():
    out = images.crop_to_ratio(_img(500, 1000), 0.0, 0.25, 1.0, 'vertical')
    assert out.size[0] == 500 and abs(_ratio(out) - 2 / 3) < 0.003 and out.size[1] <= 1000


def test_too_big_a_width_is_reduced_to_what_fits_the_height():
    out = images.crop_to_ratio(_img(300, 300), 0.0, 0.0, 1.0, 'vertical')
    assert out.size == (200, 300)


@pytest.mark.parametrize('kind,target', [('vertical', 2 / 3), ('horizontal', 616 / 353), ('icon', 1.0)])
def test_the_result_has_the_cards_ratio(kind, target):
    out = images.crop_to_ratio(_img(1200, 1600), 0.1, 0.1, 0.6, kind)
    assert abs(_ratio(out) - target) < 0.01
