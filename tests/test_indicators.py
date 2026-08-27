import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "batch"))

from indicators import (  # noqa: E402
    compute_indicators,
    compute_ma_cross,
    compute_macd,
    compute_rsi,
    compute_sma,
)


class ComputeSmaTests(unittest.TestCase):
    def test_insufficient_data_returns_none(self):
        self.assertIsNone(compute_sma([1.0, 2.0, 3.0], window=5))

    def test_averages_the_last_window_values(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        self.assertEqual(compute_sma(closes, window=3), 5.0)

    def test_exact_window_length(self):
        self.assertEqual(compute_sma([2.0, 4.0, 6.0], window=3), 4.0)


class ComputeRsiTests(unittest.TestCase):
    def test_insufficient_data_returns_none(self):
        self.assertIsNone(compute_rsi([1.0, 2.0, 3.0], period=14))

    def test_all_gains_is_100(self):
        closes = [float(i) for i in range(1, 20)]  # strictly increasing
        self.assertEqual(compute_rsi(closes, period=14), 100.0)

    def test_all_losses_is_0(self):
        closes = [float(i) for i in range(20, 1, -1)]  # strictly decreasing
        self.assertEqual(compute_rsi(closes, period=14), 0.0)

    def test_flat_series_is_neutral(self):
        closes = [10.0] * 20
        self.assertEqual(compute_rsi(closes, period=14), 100.0)


class ComputeMacdTests(unittest.TestCase):
    def test_insufficient_data_returns_none(self):
        closes = [float(i) for i in range(10)]
        self.assertIsNone(compute_macd(closes))

    def test_histogram_is_macd_minus_signal(self):
        closes = [10.0 + (i % 5) * 0.3 for i in range(60)]
        result = compute_macd(closes)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(
            result["histogram"], round(result["macd"] - result["signal"], 4), places=4
        )

    def test_uptrend_has_positive_macd(self):
        closes = [10.0 + i * 0.5 for i in range(60)]
        result = compute_macd(closes)
        self.assertGreater(result["macd"], 0)


class ComputeMaCrossTests(unittest.TestCase):
    def test_insufficient_data(self):
        closes = [float(i) for i in range(30)]
        result = compute_ma_cross(closes, short=20, long=60)
        self.assertEqual(result["state"], "insufficient_data")
        self.assertFalse(result["crossed_today"])

    def test_sustained_uptrend_is_above_no_cross(self):
        closes = [100.0 + i * 0.2 for i in range(80)]
        result = compute_ma_cross(closes, short=20, long=60)
        self.assertEqual(result["state"], "above")
        self.assertFalse(result["crossed_today"])

    def test_golden_cross_detected(self):
        # Flat history, then a sharp spike on the very last day pulls the short MA above the
        # long MA for the first time today.
        closes = [100.0] * 14 + [200.0]
        result = compute_ma_cross(closes, short=3, long=10)
        self.assertEqual(result["state"], "golden_cross")
        self.assertTrue(result["crossed_today"])

    def test_death_cross_detected(self):
        closes = [100.0] * 14 + [20.0]
        result = compute_ma_cross(closes, short=3, long=10)
        self.assertEqual(result["state"], "death_cross")
        self.assertTrue(result["crossed_today"])


class ComputeIndicatorsTests(unittest.TestCase):
    def test_shape_with_insufficient_history(self):
        history = [{"date": f"2026-01-{d:02d}", "close": 10.0 + d} for d in range(1, 6)]
        result = compute_indicators(history)
        self.assertEqual(result["data_points"], 5)
        self.assertIsNone(result["sma20"])
        self.assertIsNone(result["sma60"])
        self.assertIsNone(result["rsi14"])
        self.assertIsNone(result["macd"])
        self.assertEqual(result["ma_cross"]["state"], "insufficient_data")

    def test_ignores_rows_with_missing_close(self):
        history = [
            {"date": "2026-01-01", "close": 10.0},
            {"date": "2026-01-02", "close": None},
            {"date": "2026-01-03", "close": 12.0},
        ]
        result = compute_indicators(history)
        self.assertEqual(result["data_points"], 2)


if __name__ == "__main__":
    unittest.main()
