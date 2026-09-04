"""Unit tests for indicators.py / labels.py. Stdlib only (unittest), no new dependency.

Run with: python batch/test_indicators_labels.py
"""

from __future__ import annotations

import unittest

import indicators
import labels


def _closes_curved_down_then_up(down_n: int = 40, up_n: int = 40) -> list[float]:
    """A price series long enough for MACD (needs 26 + 9 = 35 points): an accelerating decline
    followed by an accelerating rebound. Curved (not straight-line) on purpose — a linear trend
    makes the MACD histogram hover at ~0, which flips sign on floating-point noise rather than on
    a genuine crossover."""
    down = [200 - 0.5 * i - 0.02 * i * i for i in range(down_n)]
    start = down[-1]
    up = [start + 0.5 * i + 0.02 * i * i for i in range(1, up_n + 1)]
    return down + up


class ComputeMacdTests(unittest.TestCase):
    def test_insufficient_history_returns_none(self):
        self.assertIsNone(indicators.compute_macd([100.0] * 30))

    def test_flat_prices_has_no_crossover(self):
        result = indicators.compute_macd([100.0] * 40)
        self.assertIsNotNone(result)
        self.assertFalse(result["crossed_today"])
        self.assertIn(result["state"], ("above", "below"))

    def test_detects_golden_cross_somewhere_during_a_rebound(self):
        # In production, compute_macd is re-run daily as one more close arrives. Feeding growing
        # prefixes of a down-then-up series mimics that, and a rebound after a decline must flip
        # the MACD line above its signal line at some point -> a golden_cross day should appear.
        closes = _closes_curved_down_then_up()
        states = [indicators.compute_macd(closes[:i])["state"] for i in range(35, len(closes) + 1)]
        self.assertIn("golden_cross", states)

    def test_detects_death_cross_somewhere_during_a_decline(self):
        rebound = _closes_curved_down_then_up()
        reversed_closes = [rebound[-1] - (c - rebound[0]) for c in rebound]
        states = [
            indicators.compute_macd(reversed_closes[:i])["state"]
            for i in range(35, len(reversed_closes) + 1)
        ]
        self.assertIn("death_cross", states)


class MacdLabelTests(unittest.TestCase):
    def test_none_when_no_macd(self):
        self.assertIsNone(labels.macd_label(None))

    def test_golden_cross_label_is_descriptive_not_prescriptive(self):
        text = labels.macd_label({"state": "golden_cross"})
        self.assertIn("MACD", text)
        for word in ("買", "賣", "建議"):
            self.assertNotIn(word, text)

    def test_unknown_state_returns_none(self):
        self.assertIsNone(labels.macd_label({"state": "insufficient_data"}))


class BuildLabelsIncludesMacdTests(unittest.TestCase):
    def test_build_labels_carries_macd_label(self):
        history = [
            {"date": f"2026-01-{i:02d}", "close": 100.0, "pe": 10.0, "pb": 1.0, "dividend_yield": 3.0}
            for i in range(1, 61)
        ]
        ind = indicators.compute_indicators(history)
        result = labels.build_labels(history, ind)
        self.assertIn("macd_label", result)


if __name__ == "__main__":
    unittest.main()
