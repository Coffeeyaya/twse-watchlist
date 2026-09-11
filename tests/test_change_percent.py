from indicators import compute_change_percent


def test_positive_change():
    # close 25.3, change +0.9 -> prior close 24.4
    assert compute_change_percent(25.3, 0.9) == round(0.9 / 24.4 * 100, 2)


def test_negative_change():
    # close 24.4, change -0.9 -> prior close 25.3
    assert compute_change_percent(24.4, -0.9) == round(-0.9 / 25.3 * 100, 2)


def test_no_change():
    assert compute_change_percent(100.0, 0.0) == 0.0


def test_none_close_returns_none():
    assert compute_change_percent(None, 0.9) is None


def test_none_change_returns_none():
    assert compute_change_percent(25.3, None) is None


def test_both_none_returns_none():
    assert compute_change_percent(None, None) is None


def test_zero_prior_close_returns_none():
    # close == change means prior close was 0 (e.g. a freshly-listed stock's first tick) —
    # percent change is undefined, not infinite.
    assert compute_change_percent(5.0, 5.0) is None
