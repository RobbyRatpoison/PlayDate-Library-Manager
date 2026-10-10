from images import _sgdb_options_from


def _data(*sizes, animated=()):
    return {'data': [{'url': f'u{i}', 'thumb': f't{i}', 'width': w, 'height': h,
                      'animated': i in animated} for i, (w, h) in enumerate(sizes)]}


def _urls(opts):
    return [o['url'] for o in opts]


def test_vertical_orders_by_closeness_to_two_thirds():
    # square, near-2:3, exact 2:3, wide
    out = _sgdb_options_from(_data((512, 512), (660, 930), (600, 900), (920, 430)), 'vertical')
    assert _urls(out) == ['u2', 'u1', 'u0', 'u3']


def test_equally_close_options_keep_steamgriddb_order():
    out = _sgdb_options_from(_data((600, 900), (1200, 1800), (600, 900)), 'vertical')
    assert _urls(out) == ['u0', 'u1', 'u2']


def test_icon_prefers_square():
    out = _sgdb_options_from(_data((256, 128), (64, 64), (128, 256)), 'icon')
    assert _urls(out)[0] == 'u1'


def test_horizontal_uses_the_card_ratio():
    out = _sgdb_options_from(_data((600, 900), (616, 353), (920, 430)), 'horizontal')
    assert _urls(out) == ['u1', 'u2', 'u0']


def test_unsized_options_go_last_and_animated_are_dropped():
    out = _sgdb_options_from(_data((0, 0), (600, 900), (600, 900), animated=(2,)), 'vertical')
    assert _urls(out) == ['u1', 'u0']


def test_unknown_type_keeps_original_order():
    out = _sgdb_options_from(_data((10, 100), (600, 900)), 'bogus')
    assert _urls(out) == ['u0', 'u1']


def test_fits_flag_follows_the_five_percent_rule():
    out = _sgdb_options_from(_data((600, 900), (660, 930), (512, 512), (0, 0)), 'vertical')
    fits = {o['url']: o['fits'] for o in out}
    assert fits == {'u0': True, 'u1': False, 'u2': False, 'u3': False}   # 660x930 is 6.4% off 2:3


def test_horizontal_options_do_not_fit_the_card_and_icons_always_do():
    assert not any(o['fits'] for o in _sgdb_options_from(_data((920, 430), (460, 215)), 'horizontal'))
    assert all(o['fits'] for o in _sgdb_options_from(_data((64, 64), (256, 128)), 'icon'))
