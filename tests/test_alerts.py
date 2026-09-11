"""Unit tests for batch/alerts.py — the trigger-evaluation and LINE-push logic.

Stdlib only (unittest + unittest.mock), no network calls: `requests.post` is mocked throughout.
`indicators.py`/`labels.py` are covered elsewhere (see other open PRs adding tests/ for those) —
this file focuses on the part of the pipeline that had zero coverage: turning indicator state
into alert messages, announcement dedup, and the LINE push routing/safety logic in
`send_line_push` (in particular, the test-mode/real-recipient separation the module's own
docstring calls out as something a bug here would get wrong in a way that actually reaches
people).

Run with: python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "batch"))

import alerts  # noqa: E402

_ENV_KEYS = (
    "LINE_TEST_MODE",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "LINE_RECIPIENT_USER_IDS",
    "LINE_TEST_RECIPIENT_USER_IDS",
)


class _EnvIsolatedTestCase(unittest.TestCase):
    """Snapshots and restores the LINE_* env vars around each test, so tests can freely set/unset
    them without leaking state into other tests or the real environment."""

    def setUp(self):
        self._saved_env = {key: os.environ.get(key) for key in _ENV_KEYS}
        for key in _ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class RsiBandEventTests(unittest.TestCase):
    def test_insufficient_history_returns_none(self):
        self.assertIsNone(alerts._rsi_band_event([{"close": 10.0}]))

    def test_entering_overbought_returns_event(self):
        history = [{"close": 1.0}, {"close": 2.0}]
        with patch.object(alerts.indicators_mod, "compute_rsi", side_effect=[72.0, 65.0]):
            self.assertEqual(alerts._rsi_band_event(history), "overbought_entered")

    def test_staying_overbought_does_not_re_fire(self):
        history = [{"close": 1.0}, {"close": 2.0}]
        with patch.object(alerts.indicators_mod, "compute_rsi", side_effect=[75.0, 71.0]):
            self.assertIsNone(alerts._rsi_band_event(history))

    def test_entering_oversold_returns_event(self):
        history = [{"close": 1.0}, {"close": 2.0}]
        with patch.object(alerts.indicators_mod, "compute_rsi", side_effect=[28.0, 35.0]):
            self.assertEqual(alerts._rsi_band_event(history), "oversold_entered")

    def test_missing_rsi_returns_none(self):
        history = [{"close": 1.0}, {"close": 2.0}]
        with patch.object(alerts.indicators_mod, "compute_rsi", side_effect=[None, None]):
            self.assertIsNone(alerts._rsi_band_event(history))


class EvaluateTechnicalTriggersTests(unittest.TestCase):
    def test_golden_cross_produces_one_message(self):
        indicators = {"ma_cross": {"state": "golden_cross", "crossed_today": True}}
        with patch.object(alerts, "_rsi_band_event", return_value=None):
            messages = alerts.evaluate_technical_triggers("2330", "台積電", [], indicators)
        self.assertEqual(len(messages), 1)
        self.assertIn("2330", messages[0])
        self.assertIn("黃金交叉", messages[0])

    def test_death_cross_produces_one_message(self):
        indicators = {"ma_cross": {"state": "death_cross", "crossed_today": True}}
        with patch.object(alerts, "_rsi_band_event", return_value=None):
            messages = alerts.evaluate_technical_triggers("2330", "台積電", [], indicators)
        self.assertIn("死亡交叉", messages[0])

    def test_no_message_when_ma_cross_did_not_happen_today(self):
        indicators = {"ma_cross": {"state": "above", "crossed_today": False}}
        with patch.object(alerts, "_rsi_band_event", return_value=None):
            messages = alerts.evaluate_technical_triggers("2330", "台積電", [], indicators)
        self.assertEqual(messages, [])

    def test_rsi_overbought_entry_produces_message(self):
        indicators = {"ma_cross": {"state": "above", "crossed_today": False}}
        with patch.object(alerts, "_rsi_band_event", return_value="overbought_entered"):
            messages = alerts.evaluate_technical_triggers("2330", "台積電", [], indicators)
        self.assertEqual(len(messages), 1)
        self.assertIn("超買", messages[0])

    def test_rsi_oversold_entry_produces_message(self):
        indicators = {"ma_cross": {"state": "above", "crossed_today": False}}
        with patch.object(alerts, "_rsi_band_event", return_value="oversold_entered"):
            messages = alerts.evaluate_technical_triggers("2330", "台積電", [], indicators)
        self.assertIn("超賣", messages[0])

    def test_ma_cross_and_rsi_triggers_both_fire(self):
        indicators = {"ma_cross": {"state": "golden_cross", "crossed_today": True}}
        with patch.object(alerts, "_rsi_band_event", return_value="overbought_entered"):
            messages = alerts.evaluate_technical_triggers("2330", "台積電", [], indicators)
        self.assertEqual(len(messages), 2)


class EvaluateAnnouncementTriggersTests(unittest.TestCase):
    def test_new_announcement_produces_message_and_marks_seen(self):
        news_by_code = {"2330": [{"id": "a1", "title": "某公告", "company_name": "台積電"}]}
        messages, seen = alerts.evaluate_announcement_triggers(news_by_code, set())
        self.assertEqual(len(messages), 1)
        self.assertIn("2330", messages[0])
        self.assertIn("a1", seen)

    def test_already_seen_announcement_is_skipped(self):
        news_by_code = {"2330": [{"id": "a1", "title": "某公告", "company_name": "台積電"}]}
        messages, seen = alerts.evaluate_announcement_triggers(news_by_code, {"a1"})
        self.assertEqual(messages, [])
        self.assertEqual(seen, {"a1"})

    def test_does_not_mutate_the_input_seen_ids_set(self):
        original_seen = {"a1"}
        news_by_code = {"2330": [{"id": "a2", "title": "t", "company_name": "c"}]}
        _, updated_seen = alerts.evaluate_announcement_triggers(news_by_code, original_seen)
        self.assertEqual(original_seen, {"a1"})
        self.assertEqual(updated_seen, {"a1", "a2"})


class IsTestModeTests(_EnvIsolatedTestCase):
    def test_recognized_truthy_values(self):
        for val in ("1", "true", "True", "TRUE", "yes", "YES"):
            os.environ["LINE_TEST_MODE"] = val
            self.assertTrue(alerts._is_test_mode(), msg=f"expected {val!r} to be truthy")

    def test_unset_is_false(self):
        self.assertFalse(alerts._is_test_mode())

    def test_other_values_are_false(self):
        for val in ("0", "false", "no", ""):
            os.environ["LINE_TEST_MODE"] = val
            self.assertFalse(alerts._is_test_mode(), msg=f"expected {val!r} to be falsy")


class SendLinePushTests(_EnvIsolatedTestCase):
    """`send_line_push`'s own docstring/comments call out that a test-mode push must never fall
    back to the real recipient list — these tests pin that behavior down so a future refactor
    that broke it would fail CI instead of reaching real people."""

    def test_test_mode_pushes_only_to_test_recipients_never_real(self):
        os.environ["LINE_TEST_MODE"] = "true"
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "tok"
        os.environ["LINE_RECIPIENT_USER_IDS"] = "REAL_USER_MUST_NOT_BE_PUSHED_TO"
        os.environ["LINE_TEST_RECIPIENT_USER_IDS"] = "test_user"

        with patch.object(alerts, "requests") as mock_requests:
            mock_requests.post.return_value = MagicMock(status_code=200)
            alerts.send_line_push(["hello"])

        recipients = [c.kwargs["json"]["to"] for c in mock_requests.post.call_args_list]
        self.assertEqual(recipients, ["test_user"])
        self.assertNotIn("REAL_USER_MUST_NOT_BE_PUSHED_TO", recipients)

    def test_test_mode_without_test_recipients_skips_push_entirely(self):
        os.environ["LINE_TEST_MODE"] = "true"
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "tok"
        os.environ["LINE_RECIPIENT_USER_IDS"] = "REAL_USER_MUST_NOT_BE_PUSHED_TO"
        # LINE_TEST_RECIPIENT_USER_IDS intentionally left unset.

        with patch.object(alerts, "requests") as mock_requests:
            alerts.send_line_push(["hello"])

        mock_requests.post.assert_not_called()

    def test_production_mode_uses_real_recipients(self):
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "tok"
        os.environ["LINE_RECIPIENT_USER_IDS"] = "real_user"

        with patch.object(alerts, "requests") as mock_requests:
            mock_requests.post.return_value = MagicMock(status_code=200)
            alerts.send_line_push(["hello"])

        recipients = [c.kwargs["json"]["to"] for c in mock_requests.post.call_args_list]
        self.assertEqual(recipients, ["real_user"])

    def test_test_mode_marker_and_disclaimer_are_both_present(self):
        os.environ["LINE_TEST_MODE"] = "true"
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "tok"
        os.environ["LINE_TEST_RECIPIENT_USER_IDS"] = "test_user"

        with patch.object(alerts, "requests") as mock_requests:
            mock_requests.post.return_value = MagicMock(status_code=200)
            alerts.send_line_push(["hello"])

        text = mock_requests.post.call_args.kwargs["json"]["messages"][0]["text"]
        self.assertIn(alerts.TEST_MODE_MARKER, text)
        self.assertIn(alerts.labels.DISCLAIMER, text)

    def test_production_mode_omits_test_marker(self):
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "tok"
        os.environ["LINE_RECIPIENT_USER_IDS"] = "real_user"

        with patch.object(alerts, "requests") as mock_requests:
            mock_requests.post.return_value = MagicMock(status_code=200)
            alerts.send_line_push(["hello"])

        text = mock_requests.post.call_args.kwargs["json"]["messages"][0]["text"]
        self.assertNotIn(alerts.TEST_MODE_MARKER, text)
        self.assertIn(alerts.labels.DISCLAIMER, text)

    def test_missing_token_skips_push(self):
        os.environ["LINE_RECIPIENT_USER_IDS"] = "real_user"

        with patch.object(alerts, "requests") as mock_requests:
            alerts.send_line_push(["hello"])

        mock_requests.post.assert_not_called()

    def test_missing_recipients_skips_push(self):
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "tok"

        with patch.object(alerts, "requests") as mock_requests:
            alerts.send_line_push(["hello"])

        mock_requests.post.assert_not_called()

    def test_multiple_real_recipients_each_get_a_push(self):
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "tok"
        os.environ["LINE_RECIPIENT_USER_IDS"] = "user_a, user_b"

        with patch.object(alerts, "requests") as mock_requests:
            mock_requests.post.return_value = MagicMock(status_code=200)
            alerts.send_line_push(["hello"])

        recipients = [c.kwargs["json"]["to"] for c in mock_requests.post.call_args_list]
        self.assertEqual(recipients, ["user_a", "user_b"])


if __name__ == "__main__":
    unittest.main()
