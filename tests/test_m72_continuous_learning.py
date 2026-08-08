from trading_ai.performance_learning.continuous_learning import calibration_metrics, _prob


def test_probability_normalization_accepts_fraction_or_percent():
    assert abs(_prob(.72)-.72)<1e-9
    assert abs(_prob(72)-.72)<1e-9
    assert _prob(None) is None


def test_calibration_metrics_perfect_predictions_are_better_than_inverted():
    good=calibration_metrics([(.9,1),(.8,1),(.2,0),(.1,0)])
    bad=calibration_metrics([(.1,1),(.2,1),(.8,0),(.9,0)])
    assert good['sample_size']==4
    assert good['brier_score'] < bad['brier_score']
    assert good['log_loss'] < bad['log_loss']
    assert good['expected_calibration_error'] < bad['expected_calibration_error']


def test_calibration_buckets_are_weighted_and_bounded():
    m=calibration_metrics([(.61,1),(.62,0),(.79,1),(.81,1)])
    assert m['buckets']
    assert 0 <= m['expected_calibration_error'] <= 1
    assert sum(x['count'] for x in m['buckets']) == 4
