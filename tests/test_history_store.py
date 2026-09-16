"""Unit tests for batch/history_store.py — the per-stock history read/write/merge logic.

Stdlib only (unittest + tempfile), no network calls. This module had zero test coverage on
`main` despite several earlier attempts adding tests/ for other modules (indicators.py,
labels.py, alerts.py) — this file covers the one still-untested piece: the JSON-per-stock
history store that every indicator/label computation reads from, and that the daily batch
writes to unattended. A bug in `merge_records` (e.g. picking the wrong side on a date conflict,
or dropping rows) would silently corrupt history that accumulates for years, so it's worth
pinning down before it happens rather than after.

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "batch"))

import history_store  # noqa: E402


class MergeRecordsTests(unittest.TestCase):
    def test_new_records_win_on_date_conflict(self):
        existing = [{"date": "2026-09-01", "close": 100.0}]
        new = [{"date": "2026-09-01", "close": 101.0}]
        merged = history_store.merge_records(existing, new)
        self.assertEqual(merged, [{"date": "2026-09-01", "close": 101.0}])

    def test_non_conflicting_records_are_both_kept(self):
        existing = [{"date": "2026-09-01", "close": 100.0}]
        new = [{"date": "2026-09-02", "close": 102.0}]
        merged = history_store.merge_records(existing, new)
        self.assertEqual(
            merged,
            [
                {"date": "2026-09-01", "close": 100.0},
                {"date": "2026-09-02", "close": 102.0},
            ],
        )

    def test_result_is_sorted_by_date_regardless_of_input_order(self):
        existing = [{"date": "2026-09-03", "close": 3.0}, {"date": "2026-09-01", "close": 1.0}]
        new = [{"date": "2026-09-02", "close": 2.0}]
        merged = history_store.merge_records(existing, new)
        self.assertEqual([r["date"] for r in merged], ["2026-09-01", "2026-09-02", "2026-09-03"])

    def test_does_not_mutate_inputs(self):
        existing = [{"date": "2026-09-01", "close": 100.0}]
        new = [{"date": "2026-09-01", "close": 101.0}]
        history_store.merge_records(existing, new)
        self.assertEqual(existing, [{"date": "2026-09-01", "close": 100.0}])
        self.assertEqual(new, [{"date": "2026-09-01", "close": 101.0}])

    def test_empty_new_records_returns_existing_unchanged(self):
        existing = [{"date": "2026-09-01", "close": 100.0}]
        merged = history_store.merge_records(existing, [])
        self.assertEqual(merged, existing)


class LoadSaveRoundTripTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._patcher = patch.object(history_store, "HISTORY_DIR", Path(self._tmpdir.name))
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_load_history_missing_file_returns_empty_list(self):
        self.assertEqual(history_store.load_history("9999"), [])

    def test_save_then_load_round_trips(self):
        records = [{"date": "2026-09-01", "close": 100.0}, {"date": "2026-09-02", "close": 101.5}]
        history_store.save_history("2330", records)
        self.assertEqual(history_store.load_history("2330"), records)

    def test_save_history_sorts_before_writing(self):
        records = [{"date": "2026-09-02", "close": 2.0}, {"date": "2026-09-01", "close": 1.0}]
        history_store.save_history("2330", records)
        loaded = history_store.load_history("2330")
        self.assertEqual([r["date"] for r in loaded], ["2026-09-01", "2026-09-02"])

    def test_save_history_creates_missing_directory(self):
        nested = Path(self._tmpdir.name) / "does" / "not" / "exist"
        with patch.object(history_store, "HISTORY_DIR", nested):
            history_store.save_history("2330", [{"date": "2026-09-01", "close": 1.0}])
            self.assertTrue((nested / "2330.json").exists())

    def test_different_codes_use_separate_files(self):
        history_store.save_history("2330", [{"date": "2026-09-01", "close": 1.0}])
        history_store.save_history("2454", [{"date": "2026-09-01", "close": 2.0}])
        self.assertEqual(history_store.load_history("2330")[0]["close"], 1.0)
        self.assertEqual(history_store.load_history("2454")[0]["close"], 2.0)

    def test_append_today_merges_into_existing_history(self):
        history_store.save_history("2330", [{"date": "2026-09-01", "close": 100.0}])
        history_store.append_today("2330", {"date": "2026-09-02", "close": 105.0})
        loaded = history_store.load_history("2330")
        self.assertEqual(
            loaded,
            [
                {"date": "2026-09-01", "close": 100.0},
                {"date": "2026-09-02", "close": 105.0},
            ],
        )

    def test_append_today_overwrites_same_date(self):
        history_store.save_history("2330", [{"date": "2026-09-01", "close": 100.0}])
        history_store.append_today("2330", {"date": "2026-09-01", "close": 999.0})
        self.assertEqual(history_store.load_history("2330"), [{"date": "2026-09-01", "close": 999.0}])

    def test_saved_file_is_valid_utf8_json_with_non_ascii_preserved(self):
        history_store.save_history("2330", [{"date": "2026-09-01", "close": 1.0, "name": "台積電"}])
        raw = (Path(self._tmpdir.name) / "2330.json").read_text(encoding="utf-8")
        self.assertIn("台積電", raw)


if __name__ == "__main__":
    unittest.main()
