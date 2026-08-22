"""Evaluates the v1 default trigger set (decisions.md) for watchlist tickers only, and pushes
newly-triggered events via the LINE Messaging API.

Triggers (only fire on the day the condition first becomes true, not every day it stays true):
- MA20/60 cross, either direction (uses indicators.compute_ma_cross's `crossed_today` flag).
- RSI(14) entering overbought (>=70) or oversold (<=30) — computed by comparing today's RSI
  against RSI computed on history-minus-today, so a stock that's been overbought for a week
  doesn't re-alert every day.
- New MOPS material-info announcement (see fetch_watchlist_news.py) — dedup via
  data/seen_announcements.json so a given announcement only ever fires once.

Contract (see decisions.md for the human setup this depends on): env vars
`LINE_CHANNEL_ACCESS_TOKEN` and `LINE_RECIPIENT_USER_IDS` (comma-separated LINE user IDs). Not
live-tested — the LINE Official Account doesn't exist yet.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests

import indicators as indicators_mod

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEEN_ANNOUNCEMENTS_PATH = DATA_DIR / "seen_announcements.json"

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_LINE_TEXT_LEN = 4900  # API limit is 5000; leave headroom


def _rsi_band_event(history: list[dict]) -> str | None:
    closes_today = [r["close"] for r in history if r.get("close") is not None]
    if len(closes_today) < 2:
        return None
    rsi_today = indicators_mod.compute_rsi(closes_today)
    rsi_yesterday = indicators_mod.compute_rsi(closes_today[:-1])
    if rsi_today is None or rsi_yesterday is None:
        return None
    if rsi_yesterday < 70 <= rsi_today:
        return "overbought_entered"
    if rsi_yesterday > 30 >= rsi_today:
        return "oversold_entered"
    return None


def evaluate_technical_triggers(code: str, name: str, history: list[dict], indicators: dict) -> list[str]:
    messages = []
    cross = indicators.get("ma_cross") or {}
    if cross.get("crossed_today"):
        label = "黃金交叉" if cross["state"] == "golden_cross" else "死亡交叉"
        messages.append(f"📈 {code} {name}：今日出現{label}（20日均線／60日均線）")

    rsi_event = _rsi_band_event(history)
    if rsi_event == "overbought_entered":
        messages.append(f"⚠️ {code} {name}：RSI(14) 今日進入超買區（>=70）")
    elif rsi_event == "oversold_entered":
        messages.append(f"⚠️ {code} {name}：RSI(14) 今日進入超賣區（<=30）")

    return messages


def _load_seen_announcement_ids() -> set[str]:
    if not SEEN_ANNOUNCEMENTS_PATH.exists():
        return set()
    with SEEN_ANNOUNCEMENTS_PATH.open(encoding="utf-8") as f:
        return set(json.load(f))


def _save_seen_announcement_ids(ids: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SEEN_ANNOUNCEMENTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False)


def evaluate_announcement_triggers(
    news_by_code: dict[str, list[dict]], seen_ids: set[str]
) -> tuple[list[str], set[str]]:
    """`news_by_code` = {code: [{"id", "title", "date", "company_name"}, ...]}. Returns
    (new alert messages, updated seen-ids set)."""
    messages = []
    newly_seen = set(seen_ids)
    for code, announcements in news_by_code.items():
        for ann in announcements:
            if ann["id"] in seen_ids:
                continue
            newly_seen.add(ann["id"])
            messages.append(f"📢 {code} {ann.get('company_name', '')}：{ann['title']}")
    return messages, newly_seen


def send_line_push(messages: list[str]) -> None:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    recipient_ids_raw = os.environ.get("LINE_RECIPIENT_USER_IDS", "")
    if not token or not recipient_ids_raw:
        log.warning("LINE not configured (missing token or recipient IDs) — skipping push")
        return

    recipients = [r.strip() for r in recipient_ids_raw.split(",") if r.strip()]
    text = "\n".join(messages)
    if len(text) > MAX_LINE_TEXT_LEN:
        text = text[:MAX_LINE_TEXT_LEN] + "\n…(訊息過長，已截斷)"

    for user_id in recipients:
        resp = requests.post(
            LINE_PUSH_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"to": user_id, "messages": [{"type": "text", "text": text}]},
            timeout=20,
        )
        if resp.status_code != 200:
            log.error("LINE push to %s failed: %s %s", user_id, resp.status_code, resp.text)
        else:
            log.info("LINE push sent to %s", user_id)


def run(
    watchlist_codes: list[str],
    dashboard_stocks_by_code: dict[str, dict],
    history_by_code: dict[str, list[dict]],
    news_by_code: dict[str, list[dict]] | None = None,
) -> list[str]:
    """Evaluates all triggers for the watchlist and pushes via LINE. Returns the messages sent
    (empty list if nothing triggered or LINE isn't configured yet)."""
    messages = []
    for code in watchlist_codes:
        stock = dashboard_stocks_by_code.get(code)
        history = history_by_code.get(code, [])
        if not stock:
            log.warning("Watchlist code %s not found in today's snapshot, skipping", code)
            continue
        messages.extend(
            evaluate_technical_triggers(code, stock.get("name", ""), history, stock.get("indicators", {}))
        )

    if news_by_code:
        seen_ids = _load_seen_announcement_ids()
        ann_messages, updated_seen = evaluate_announcement_triggers(news_by_code, seen_ids)
        messages.extend(ann_messages)
        _save_seen_announcement_ids(updated_seen)

    if messages:
        log.info("%d trigger(s) fired today", len(messages))
        send_line_push(messages)
    else:
        log.info("No triggers fired today")

    return messages
