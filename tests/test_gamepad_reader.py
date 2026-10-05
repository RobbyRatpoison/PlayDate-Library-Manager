"""gamepad_reader: the page-facing state built from raw evdev values (no device needed)."""
import gamepad_reader as gr


def _reader(desktop=False):
    r = gr.GamepadReader(lambda s: None, desktop=desktop)
    # an xpad-style pad: triggers on ABS_Z/RZ (0..255), right stick on ABS_RX/RY, sticks signed 16-bit
    r._rng = {gr._ABS_X: (-32768, 32767), gr._ABS_Y: (-32768, 32767), gr._ABS_RX: (-32768, 32767), gr._ABS_RY: (-32768, 32767),
              gr._ABS_Z: (0, 255), gr._ABS_RZ: (0, 255)}
    r._trig = {gr._ABS_Z: 0, gr._ABS_RZ: 0}
    return r


def _state(r):
    out = []
    r._on_state = out.append
    r._emit()
    return out[0]


def test_dpad_hat_becomes_standard_buttons_12_to_15():
    r = _reader()
    r._abs[gr._ABS_HAT0Y] = 1
    r._abs[gr._ABS_HAT0X] = -1
    b = _state(r)['buttons']
    assert [b[i]['pressed'] for i in (12, 13, 14, 15)] == [False, True, True, False]


def test_triggers_are_buttons_6_and_7_and_not_axes():
    r = _reader()
    r._trig[gr._ABS_Z] = 255
    s = _state(r)
    assert s['buttons'][6]['pressed'] and not s['buttons'][7]['pressed']
    assert len(s['axes']) == 4 and s['axes'] == [0.0, 0.0, 0.0, 0.0] or all(abs(a) < 0.01 for a in s['axes'])


def test_pad_id_is_the_deck_one_unless_desktop():
    assert _state(_reader())['id'] == 'Steam Deck (evdev)'
    r = _reader(desktop=True)
    r._ident = '8BitDo Ultimate 2 (Vendor: 2dc8 Product: 310b)'
    assert _state(r)['id'] == '8BitDo Ultimate 2 (Vendor: 2dc8 Product: 310b)'
    assert _state(r)['mapping'] == 'standard'
