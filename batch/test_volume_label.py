"""Unit tests for the volume-ratio indicator + descriptive label added 2026-09-11.

Uses stdlib unittest (no new dependency) since the repo currently has no test runner wired up.
Run directly: python3 batch/test_volume_label.py
"""

from __future__ import annotations

import unittest

from indicators import compute_indicators, compute_volume_ratio
from labels import build_labels, volume_label


def _history(volumes: list[float | None], closes: list[float] | None = None) -> list[dict]:
    closes = closes or [100.0] * len(volumes)
    return [
        {"date": f"2026-01-{i + 1:02d}", "close": c, "pe": None, "pb": None,
         "dividend_yield": None, "volume": v}
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


class ComputeVolumeRatioTests(unittest.TestCase):
    def test_insufficient_history_returns_none(self):
        history = _history([1000] * 20)  # needs 21 (window=20 + today)
        self.assertIsNone(compute_volume_ratio(history))

    def test_missing_volume_keys_are_ignored_not_zero(self):
        history = _history([None] * 5 + [1000] * 21)
        self.assertEqual(compute_volume_ratio(history), 1.0)

    def test_spike_ratio(self):
        history = _history([1000] * 20 + [3000])
        self.assertEqual(compute_volume_ratio(history), 3.0)

    def test_shrink_ratio(self):
        history = _history([1000] * 20 + [200])
        self.assertEqual(compute_volume_ratio(history), 0.2)

    def test_baseline_excludes_todays_volume(self):
        # Baseline should be the average of the 20 days BEFORE today, not including today.
        history = _history([500] * 20 + [1500])
        self.assertEqual(compute_volume_ratio(history), 3.0)

    def test_zero_baseline_avoids_division_by_zero(self):
        history = _history([0] * 20 + [500])
        self.assertIsNone(compute_volume_ratio(history))

    def test_compute_indicators_includes_volume_ratio_key(self):
        history = _history([1000] * 20 + [3000])
        ind = compute_indicators(history)
        self.assertEqual(ind["volume_ratio_20"], 3.0)


class VolumeLabelTests(unittest.TestCase):
    def test_none_when_no_ratio(self):
        self.assertIsNone(volume_label(None))

    def test_spike_wording(self):
        self.assertEqual(volume_label(2.5), "今日成交量明顯放大，約為近20日均量的 2.5 倍")

    def test_shrink_wording(self):
        self.assertEqual(volume_label(0.3), "今日成交量明顯萎縮，約為近20日均量的 0.3 倍")

    def test_neutral_wording_at_boundaries(self):
        self.assertEqual(volume_label(2.0), "今日成交量明顯放大，約為近20日均量的 2.0 倍")
        self.assertEqual(volume_label(0.5), "今日成交量明顯萎縮，約為近20日均量的 0.5 倍")
        self.assertEqual(volume_label(1.0), "今日成交量與近20日均量相近")

    def test_never_a_buy_sell_recommendation(self):
        for ratio in (0.1, 0.5, 1.0, 2.0, 5.0):
            text = volume_label(ratio)
            for banned in ("買", "賣", "建議"):
                self.assertNotIn(banned, text)


class BuildLabelsIntegrationTests(unittest.TestCase):
    def test_build_labels_wires_volume_label_through(self):
        history = _history([1000] * 20 + [4000])
        ind = compute_indicators(history)
        lbl = build_labels(history, ind)
        self.assertIn("volume_label", lbl)
        self.assertEqual(lbl["volume_label"], "今日成交量明顯放大，約為近20日均量的 4.0 倍")

    def test_old_history_without_volume_key_degrades_gracefully(self):
        # Records written before 2026-09-11 have no "volume" key at all.
        history = [
            {"date": f"2026-01-{i + 1:02d}", "close": 100.0, "pe": None, "pb": None,
             "dividend_yield": None}
            for i in range(25)
        ]
        ind = compute_indicators(history)
        lbl = build_labels(history, ind)
        self.assertIsNone(ind["volume_ratio_20"])
        self.assertIsNone(lbl["volume_label"])


if __name__ == "__main__":
    unittest.main()
