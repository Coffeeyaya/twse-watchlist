from indicators import (
    compute_indicators,
    compute_ma_cross,
    compute_macd,
    compute_rsi,
    compute_sma,
)


def test_compute_sma_insufficient_data_returns_none():
    assert compute_sma([1, 2, 3], 5) is None


def test_compute_sma_uses_most_recent_window():
    assert compute_sma([1, 2, 3, 4, 5], 5) == 3.0
    assert compute_sma([1, 2, 3, 4, 5], 3) == 4.0


def test_compute_rsi_insufficient_data_returns_none():
    assert compute_rsi([1.0] * 10, period=14) is None


def test_compute_rsi_all_gains_is_100():
    closes = [float(i) for i in range(1, 20)]  # strictly increasing
    assert compute_rsi(closes, period=14) == 100.0


def test_compute_rsi_all_losses_is_0():
    closes = [float(i) for i in range(20, 1, -1)]  # strictly decreasing
    assert compute_rsi(closes, period=14) == 0.0


def test_compute_macd_insufficient_data_returns_none():
    assert compute_macd([1.0] * 30) is None


def test_compute_macd_flat_series_is_near_zero():
    closes = [100.0] * 40
    result = compute_macd(closes)
    assert result is not None
    assert result["macd"] == 0.0
    assert result["signal"] == 0.0
    assert result["histogram"] == 0.0


def test_compute_ma_cross_insufficient_data():
    result = compute_ma_cross([1.0, 2.0, 3.0], short=2, long=4)
    assert result == {"state": "insufficient_data", "crossed_today": False}


def test_compute_ma_cross_detects_golden_cross_today():
    # short(2)/long(4) MA are tied through day 5, then a jump on the last day pushes the short
    # MA above the long MA — a golden cross on the most recent day only.
    closes = [10, 10, 10, 10, 10, 20]
    result = compute_ma_cross(closes, short=2, long=4)
    assert result == {"state": "golden_cross", "crossed_today": True}


def test_compute_ma_cross_detects_death_cross_today():
    closes = [10, 10, 10, 10, 10, 0]
    result = compute_ma_cross(closes, short=2, long=4)
    assert result == {"state": "death_cross", "crossed_today": True}


def test_compute_ma_cross_steady_state_no_cross():
    closes = [1, 2, 3, 4, 5, 6, 7, 8]
    result = compute_ma_cross(closes, short=2, long=4)
    assert result["state"] == "above"
    assert result["crossed_today"] is False


def test_compute_indicators_shape_with_short_history():
    history = [{"date": f"2026-01-{d:02d}", "close": float(d)} for d in range(1, 6)]
    result = compute_indicators(history)
    assert result["data_points"] == 5
    assert result["sma20"] is None
    assert result["sma60"] is None
    assert result["rsi14"] is None
    assert result["macd"] is None
    assert result["ma_cross"]["state"] == "insufficient_data"


def test_compute_indicators_ignores_missing_closes():
    history = [
        {"date": "2026-01-01", "close": 10.0},
        {"date": "2026-01-02", "close": None},
        {"date": "2026-01-03", "close": 12.0},
    ]
    result = compute_indicators(history)
    assert result["data_points"] == 2
