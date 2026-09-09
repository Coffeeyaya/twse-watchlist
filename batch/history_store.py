"""Per-stock historical record store: data/history/<code>.json, one JSON array per stock.

Kept intentionally minimal (date, close, pe, pb, dividend_yield only) — this is what
indicators.py/labels.py need for SMA/RSI/MACD and valuation percentiles. Today's full OHLC lives
only in data/market_snapshot.json, not accumulated here (see decisions.md in the coordination
project for why).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"


def atomic_write_json(path: Path, data) -> None:
    """Write `data` as JSON to `path` without ever leaving a truncated/corrupt file behind.

    Writes to a sibling temp file first, then atomically renames it onto the destination
    (os.replace is atomic on POSIX and Windows). If the process is killed mid-write — a GitHub
    Actions job timeout, an OOM, a runner eviction — the temp file is what's left half-written,
    and `path` itself is untouched, so the next run can't crash on a corrupted JSON file it
    reads back.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp{os.getpid()}")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def load_history(code: str) -> list[dict]:
    path = HISTORY_DIR / f"{code}.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_history(code: str, records: list[dict]) -> None:
    records = sorted(records, key=lambda r: r["date"])
    path = HISTORY_DIR / f"{code}.json"
    atomic_write_json(path, records)


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
