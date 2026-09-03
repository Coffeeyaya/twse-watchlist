import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "batch"))

from labels import (  # noqa: E402
    DISCLAIMER,
    build_labels,
    ma_cross_label,
    percentile_rank,
    rsi_label,
    valuation_labels,
)


class PercentileRankTests(unittest.TestCase):
    def test_none_value_returns_none(self):
        self.assertIsNone(percentile_rank(None, [1.0, 2.0, 3.0]))

    def test_empty_series_returns_none(self):
        self.assertIsNone(percentile_rank(5.0, []))

    def test_series_with_only_nones_returns_none(self):
        self.assertIsNone(percentile_rank(5.0, [None, None]))

    def test_lowest_value_is_low_percentile(self):
        self.assertEqual(percentile_rank(1.0, [1.0, 2.0, 3.0, 4.0, 5.0]), 20.0)

    def test_highest_value_is_100(self):
        self.assertEqual(percentile_rank(5.0, [1.0, 2.0, 3.0, 4.0, 5.0]), 100.0)

    def test_ignores_none_entries_in_series(self):
        self.assertEqual(percentile_rank(2.0, [1.0, None, 2.0, None, 3.0]), round(200 / 3, 1))


class ValuationLabelsTests(unittest.TestCase):
    def test_empty_history_returns_all_none(self):
        result = valuation_labels([])
        self.assertIsNone(result["pe_percentile"])
        self.assertIsNone(result["pe_label"])
        self.assertEqual(result["lookback_days"], 0)
        self.assertIsNone(result["lookback_start_date"])

    def test_cheap_pe_gets_cheap_label(self):
        # Latest close has the lowest PE in its own history -> 3rd of 10 <= 20th percentile.
        history = [
            {"date": f"2026-01-{d:02d}", "pe": float(p), "pb": None, "dividend_yield": None}
            for d, p in zip(range(1, 11), [20, 19, 18, 17, 16, 15, 14, 13, 12, 1])
        ]
        result = valuation_labels(history)
        self.assertEqual(result["pe_label"], "相對自身歷史便宜")
        self.assertEqual(result["lookback_days"], 10)
        self.assertEqual(result["lookback_start_date"], "2026-01-01")

    def test_expensive_pe_gets_expensive_label(self):
        history = [
            {"date": f"2026-01-{d:02d}", "pe": float(p), "pb": None, "dividend_yield": None}
            for d, p in zip(range(1, 11), [1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        ]
        result = valuation_labels(history)
        self.assertEqual(result["pe_label"], "相對自身歷史昂貴")

    def test_high_dividend_yield_gets_high_label_not_cheap(self):
        # low_is_cheap=False for dividend yield: a high percentile is a descriptive
        # "relatively high yield" label, never phrased as cheap/expensive.
        history = [
            {"date": f"2026-01-{d:02d}", "pe": None, "pb": None, "dividend_yield": float(y)}
            for d, y in zip(range(1, 11), [1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        ]
        result = valuation_labels(history)
        self.assertEqual(result["dividend_yield_label"], "殖利率處於自身歷史相對高點")


class RsiLabelTests(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(rsi_label(None))

    def test_overbought(self):
        self.assertEqual(rsi_label(70), "RSI 顯示超買")
        self.assertEqual(rsi_label(85), "RSI 顯示超買")

    def test_oversold(self):
        self.assertEqual(rsi_label(30), "RSI 顯示超賣")
        self.assertEqual(rsi_label(10), "RSI 顯示超賣")

    def test_neutral(self):
        self.assertEqual(rsi_label(50), "RSI 中性")


class MaCrossLabelTests(unittest.TestCase):
    def test_none_input_returns_none(self):
        self.assertIsNone(ma_cross_label(None))

    def test_known_states_map_to_chinese_labels(self):
        for state in ("golden_cross", "death_cross", "above", "below", "insufficient_data"):
            label = ma_cross_label({"state": state})
            self.assertIsNotNone(label)
            self.assertIsInstance(label, str)

    def test_unknown_state_returns_none(self):
        self.assertIsNone(ma_cross_label({"state": "some_future_state"}))


class BuildLabelsTests(unittest.TestCase):
    def test_disclaimer_text_is_exact(self):
        # This exact sentence is a hard product requirement — every user-facing surface must
        # carry it verbatim. A test guards against it drifting during unrelated edits.
        self.assertEqual(
            DISCLAIMER,
            "本工具僅呈現公開數據與依規則計算的描述性標籤，不構成任何買賣建議，投資決策請自行判斷。",
        )

    def test_build_labels_includes_disclaimer(self):
        result = build_labels([], {"rsi14": None, "ma_cross": None})
        self.assertEqual(result["disclaimer"], DISCLAIMER)

    def test_build_labels_merges_valuation_and_indicator_labels(self):
        history = [{"date": "2026-01-01", "pe": 10.0, "pb": 1.0, "dividend_yield": 3.0}]
        indicators = {"rsi14": 75, "ma_cross": {"state": "golden_cross"}}
        result = build_labels(history, indicators)
        self.assertEqual(result["rsi_label"], "RSI 顯示超買")
        self.assertEqual(result["ma_cross_label"], "今日出現黃金交叉（20日均線上穿60日均線）")
        self.assertEqual(result["pe_percentile"], 100.0)


if __name__ == "__main__":
    unittest.main()
