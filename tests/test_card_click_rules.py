"""Mouse actions on game cards: the saved rule list is validated, and the old
require_double_click_launch setting migrates into it."""
import json

import pytest

import config


def rule(button, click, action):
    return {'button': button, 'click': click, 'action': action}


def test_normalize_drops_invalid_and_duplicate_rules():
    rules = [
        rule('left', 'single', 'launch'),
        rule('left', 'single', 'edit'),          # same button + click: first one wins
        rule('bogus', 'single', 'launch'),       # unknown button
        rule('left', 'triple', 'launch'),        # unknown click type
        rule('middle', 'single', 'delete'),      # delete is not an allowed action
        'not a rule',
        rule('back', 'double', 'none'),
    ]
    assert config.normalize_card_click_rules(rules) == [rule('left', 'single', 'launch'), rule('back', 'double', 'none')]


def test_normalize_keeps_an_empty_list_and_rejects_non_lists():
    assert config.normalize_card_click_rules([]) == []
    assert config.normalize_card_click_rules(None) == []
    assert config.normalize_card_click_rules({'button': 'left'}) == []


def test_defaults_are_valid_and_unchanged_by_normalizing():
    assert config.normalize_card_click_rules(config.DEFAULT_CARD_CLICK_RULES) == config.DEFAULT_CARD_CLICK_RULES


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / 'state.json'
    monkeypatch.setattr(config, 'STATE_PATH', str(path))

    def write(**extra):
        state = json.loads(json.dumps(config.DEFAULT_STATE))
        state.pop('card_click_rules', None)
        state.update(extra)
        path.write_text(json.dumps(state))

    write.path = path
    return write


def load(state_file):
    return config.load_state(), json.loads(state_file.path.read_text())


def test_migration_turns_the_double_click_setting_into_a_double_click_launch_rule(state_file):
    state_file(require_double_click_launch=True)
    state, on_disk = load(state_file)
    assert state['card_click_rules'][0] == rule('left', 'double', 'launch')
    assert rule('right', 'single', 'context_menu') in state['card_click_rules']
    assert 'require_double_click_launch' not in on_disk


def test_migration_with_the_setting_off_gives_the_defaults(state_file):
    state_file(require_double_click_launch=False)
    state, _ = load(state_file)
    assert state['card_click_rules'] == config.DEFAULT_CARD_CLICK_RULES


def test_a_restored_old_state_never_overwrites_rules_the_user_already_set(state_file):
    mine = [rule('middle', 'single', 'store')]
    state_file(require_double_click_launch=True, card_click_rules=mine)
    state, on_disk = load(state_file)
    assert state['card_click_rules'] == mine
    assert 'require_double_click_launch' not in on_disk


def test_save_state_validates_rules(state_file):
    state_file()
    config.save_state({'card_click_rules': [rule('right', 'single', 'edit'), rule('right', 'single', 'launch'), rule('x', 'single', 'edit')]})
    assert config.load_state()['card_click_rules'] == [rule('right', 'single', 'edit')]


def test_gamepad_shortcut_remaps_are_accepted_and_unknown_actions_dropped(state_file):
    state_file()
    config.save_state({'button_remaps': {'10': 'sc_store', '3': 'none', '4': 'rm_rf', 'x': 'a'}})
    assert config.load_state()['button_remaps'] == {'10': 'sc_store', '3': 'none'}
