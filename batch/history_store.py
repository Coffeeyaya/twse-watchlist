"""Per-stock historical record store: data/history/<code>.json, one JSON array per stock.

Kept intentionally minimal (date, close, pe, pb, dividend_yield only) — this is what
indicators.py/labels.py need for SMA/RSI/MACD and valuation percentiles. Today's full OHLC lives
only in data/market_snapshot.json, not accumulated here (see decisions.md in the coordination
project for why).
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"


def load_history(code: str) -> list[dict]:
    path = HISTORY_DIR / f"{code}.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_history(code: str, records: list[dict]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    records = sorted(records, key=lambda r: r["date"])
    path = HISTORY_DIR / f"{code}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"))


def merge_records(existing: list[dict], new_records: list[dict]) -> list[dict]:
    """Merge by date, new_records wins on conflict. Returns a new sorted list."""
    by_date = {r["date"]: r for r in existing}
    for r in new_records:
        by_date[r["date"]] = r
    return sorted(by_date.values(), key=lambda r: r["date"])


def append_today(code: str, record: dict) -> None:
    existing = load_history(code)
    merged = merge_records(existing, [record])
    save_history(code, merged)
