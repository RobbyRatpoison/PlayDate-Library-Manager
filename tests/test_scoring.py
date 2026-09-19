"""Review confidence weighting (utils.weighted_review_score) and
Steam-style review labels (utils.review_score_label)."""
import pytest

from utils import review_score_label, weighted_review_score as _weighted_score


def test_zero_reviews_scores_zero():
    assert _weighted_score(100, 0) == 0


def test_neutral_score_stays_neutral_regardless_of_count():
    assert _weighted_score(50, 1) == 50
    assert _weighted_score(50, 100000) == 50


def test_low_count_pulled_toward_fifty():
    # 100% with 9 reviews: log10(10)=1 → halfway pulled back → 75.
    assert _weighted_score(100, 9) == 75
    # 100% with 99 reviews: log10(100)=2 → quarter pulled back.
    assert _weighted_score(100, 99) == 88


def test_negative_scores_pulled_up_toward_fifty():
    assert _weighted_score(0, 9) == 25


def test_high_count_approaches_raw_score():
    assert _weighted_score(90, 999999) - 90 <= 1


def test_pull_weakens_as_count_grows():
    scores = [_weighted_score(100, n) for n in (9, 99, 999, 9999)]
    assert scores == sorted(scores)
    assert scores[0] < scores[-1] <= 100


def test_default_half_trust_matches_original_fixed_curve():
    import math
    for pct in (0, 30, 75, 100):
        for n in (1, 9, 50, 500, 12345):
            legacy = round(((pct / 100) - ((pct / 100) - 0.5) * (2 ** (-math.log10(n + 1)))) * 100)
            assert _weighted_score(pct, n) == legacy


def test_larger_half_trust_distrusts_small_samples_for_longer():
    assert _weighted_score(100, 99, half_trust=100) < _weighted_score(100, 99)
    assert _weighted_score(100, 99, half_trust=3) > _weighted_score(100, 99)


def test_half_trust_is_the_count_plus_one_that_halves_the_pull():
    # At count + 1 == half_trust the raw score is trusted exactly halfway.
    assert _weighted_score(100, 29, half_trust=30) == 75
    assert _weighted_score(0, 199, half_trust=200) == 25


def test_half_trust_is_clamped_to_a_sane_minimum():
    assert _weighted_score(100, 5, half_trust=0) == _weighted_score(100, 5, half_trust=2)


@pytest.mark.parametrize("percent,total,label", [
    (100, 0,    'No Reviews'),
    (100, 9,    'Not Enough Reviews'),
    (96,  500,  'Overwhelmingly Positive'),
    (96,  499,  'Very Positive'),   # count too low for Overwhelmingly
    (85,  100,  'Very Positive'),
    (85,  20,   'Positive'),        # positive but fewer than 50 reviews
    (75,  100,  'Mostly Positive'),
    (55,  100,  'Mixed'),
    (30,  100,  'Mostly Negative'),
    (10,  600,  'Overwhelmingly Negative'),
    (10,  60,   'Very Negative'),
    (10,  20,   'Negative'),
])
def test_review_score_label(percent, total, label):
    assert review_score_label(percent, total) == label
