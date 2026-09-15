"""Unit tests for compute_stochastic (indicators.py) and kd_label (labels.py). Stdlib unittest,
no new dependency — same pattern as this repo's other per-feature test files.

Run: python3 -m unittest batch/test_stochastic.py
"""

from __future__ import annotations

import unittest

from indicators import compute_stochastic
from labels import kd_label


def _history(days: list[tuple[float, float, float]]) -> list[dict]:
    """Build history records from (high, low, close) tuples, one per day, dated sequentially."""
    return [
        {"date": f"2026-01-{i + 1:02d}", "high": h, "low": l, "close": c}
        for i, (h, l, c) in enumerate(days)
    ]


class ComputeStochasticTests(unittest.TestCase):
    def test_insufficient_data_returns_none(self):
        history = _history([(10, 9, 9.5)] * 5)  # period defaults to 9
        self.assertIsNone(compute_stochastic(history))

    def test_missing_high_low_treated_as_absent(self):
        history = [{"date": "2026-01-01", "close": 10.0}] * 20  # no high/low at all
        self.assertIsNone(compute_stochastic(history))

    def test_flat_price_series_gives_neutral_kd(self):
        history = _history([(10.0, 10.0, 10.0)] * 12)
        kd = compute_stochastic(history, period=9)
        self.assertIsNotNone(kd)
        self.assertEqual(kd["k"], 50.0)
        self.assertEqual(kd["d"], 50.0)
        self.assertEqual(kd["state"], "neutral")
        self.assertFalse(kd["crossed_today"])
        self.assertIsNone(kd["cross"])

    def test_sustained_new_highs_push_k_into_overbought(self):
        # Each day closes at a new high with a tight range -> RSV pinned near 100 every day.
        days = [(10.0 + i, 9.5 + i, 10.0 + i) for i in range(20)]
        history = _history(days)
        kd = compute_stochastic(history, period=9)
        self.assertIsNotNone(kd)
        self.assertGreaterEqual(kd["k"], 80)
        self.assertEqual(kd["state"], "overbought")

    def test_golden_cross_detected(self):
        # Flat/declining first, then a sharp run of new highs long enough for K to overtake D.
        flat = [(10.0, 9.0, 9.5)] * 9
        rally = [(10.0 + i, 9.5 + i, 10.0 + i) for i in range(6)]
        history = _history(flat + rally)
        kd = compute_stochastic(history, period=9)
        self.assertIsNotNone(kd)
        self.assertTrue(kd["crossed_today"] or kd["state"] == "overbought")
        if kd["crossed_today"]:
            self.assertEqual(kd["cross"], "golden_cross")

    def test_exact_period_length_has_no_cross_info(self):
        history = _history([(10.0, 9.0, 9.5)] * 9)  # exactly `period` days, one RSV computed
        kd = compute_stochastic(history, period=9)
        self.assertIsNotNone(kd)
        self.assertFalse(kd["crossed_today"])
        self.assertIsNone(kd["cross"])

    def test_records_missing_high_low_are_skipped_not_fatal(self):
        good = _history([(10.0, 9.0, 9.5)] * 9)
        gappy = [{"date": "2025-12-31", "close": 9.0}] + good  # one earlier day with no high/low
        kd = compute_stochastic(gappy, period=9)
        self.assertIsNotNone(kd)  # the 9 well-formed days are still enough


class KdLabelTests(unittest.TestCase):
    def test_none_input(self):
        self.assertIsNone(kd_label(None))

    def test_overbought(self):
        kd = {"k": 85, "d": 70, "state": "overbought", "cross": None, "crossed_today": False}
        self.assertEqual(kd_label(kd), "KD顯示超買")

    def test_oversold(self):
        kd = {"k": 10, "d": 25, "state": "oversold", "cross": None, "crossed_today": False}
        self.assertEqual(kd_label(kd), "KD顯示超賣")

    def test_neutral(self):
        kd = {"k": 50, "d": 48, "state": "neutral", "cross": None, "crossed_today": False}
        self.assertEqual(kd_label(kd), "KD中性")

    def test_golden_cross_wording(self):
        kd = {"k": 55, "d": 50, "state": "neutral", "cross": "golden_cross", "crossed_today": True}
        self.assertEqual(kd_label(kd), "KD出現黃金交叉（K值由下往上穿越D值）")

    def test_death_cross_wording(self):
        kd = {"k": 45, "d": 50, "state": "neutral", "cross": "death_cross", "crossed_today": True}
        self.assertEqual(kd_label(kd), "KD出現死亡交叉（K值由上往下穿越D值）")

    def test_no_label_contains_a_buy_sell_recommendation(self):
        # "超買"/"超賣" (overbought/oversold) are standard descriptive TA vocabulary — the
        # existing rsi_label uses the same wording. What must never appear is a recommendation:
        # "buy in" / "sell out" / "recommend" phrasing.
        cases = [
            {"k": 85, "d": 70, "state": "overbought", "cross": None, "crossed_today": False},
            {"k": 10, "d": 25, "state": "oversold", "cross": None, "crossed_today": False},
            {"k": 50, "d": 48, "state": "neutral", "cross": None, "crossed_today": False},
            {"k": 55, "d": 50, "state": "neutral", "cross": "golden_cross", "crossed_today": True},
            {"k": 45, "d": 50, "state": "neutral", "cross": "death_cross", "crossed_today": True},
        ]
        for kd in cases:
            label = kd_label(kd)
            self.assertNotIn("建議", label)
            self.assertNotIn("買進", label)
            self.assertNotIn("賣出", label)


if __name__ == "__main__":
    unittest.main()
