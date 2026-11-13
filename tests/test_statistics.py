import pytest

from agentprobe.statistics import agreement, bootstrap_delta


def test_cohens_kappa_matches_hand_computed_table():
    # 3 yes/yes, 1 yes/no, 1 no/yes, 3 no/no: po=.75, pe=.5.
    result = agreement(
        [True] * 4 + [False] * 4, [True, True, True, False, True, False, False, False]
    )
    assert result.agreement == 0.75
    assert result.kappa == 0.5
    assert result.n == 8
    assert "low_kappa" in result.warnings
    assert "small_sample" in result.warnings


def test_perfect_single_class_has_undefined_kappa():
    result = agreement([True] * 25, [True] * 25)
    assert result.agreement == 1
    assert result.kappa is None
    assert "undefined_kappa" in result.warnings


@pytest.mark.parametrize("left,right", [([], []), ([True], []), ([1], [True])])
def test_agreement_rejects_invalid_pairs(left, right):
    with pytest.raises(ValueError):
        agreement(left, right)


def test_bootstrap_detects_regression_and_is_reproducible():
    deltas = [-1.0] * 12 + [0.0] * 12
    first = bootstrap_delta(deltas, seed=7, samples=2000)
    assert first == bootstrap_delta(deltas, seed=7, samples=2000)
    assert first.delta == -0.5
    assert first.ci_high < 0
    assert first.regressed
    assert first.ci_low <= first.delta <= first.ci_high


def test_no_change_and_improvement_are_not_regressions():
    assert not bootstrap_delta([0.0] * 20, seed=7, samples=100).regressed
    result = bootstrap_delta([1.0] * 20, seed=7, samples=100)
    assert result.ci_low == result.ci_high == result.delta == 1
    assert not result.regressed


@pytest.mark.parametrize(
    "deltas,samples", [([], 100), ([1], 100), ([float("nan"), 0], 100), ([0, 0], 99)]
)
def test_bootstrap_validates_inputs(deltas, samples):
    with pytest.raises(ValueError):
        bootstrap_delta(deltas, seed=1, samples=samples)
