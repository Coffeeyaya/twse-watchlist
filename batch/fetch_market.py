"""Daily incremental fetch: today's full-market snapshot (OHLC + valuation) for every TWSE-listed
common stock, and one new history record per stock appended to data/history/<code>.json.

Universe = codes present in BWIBBU_ALL (openapi's daily P/E/P/B/yield endpoint), which naturally
excludes ETFs/warrants/bonds — see decisions.md for why this is the "any TWSE-listed stock" filter.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import history_store
import twse_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_PATH = DATA_DIR / "market_snapshot.json"


def fetch_today_snapshot() -> list[dict]:
    """One record per stock: full OHLC + valuation, for today. Universe = BWIBBU codes."""
    ohlc = twse_client.fetch_today_ohlc()
    valuation = twse_client.fetch_today_valuation()

    universe = valuation.keys()
    missing_ohlc = [code for code in universe if code not in ohlc]
    if missing_ohlc:
        log.warning(
            "%d stocks have valuation data but no OHLC today (likely suspended): %s",
            len(missing_ohlc),
            ", ".join(missing_ohlc[:10]) + ("..." if len(missing_ohlc) > 10 else ""),
        )

    snapshot = []
    for code, val in valuation.items():
        row = ohlc.get(code, {})
        snapshot.append(
            {
                "code": code,
                "name": val.get("name") or row.get("name"),
                "date": val["date"],
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "change": row.get("change"),
                "volume": row.get("volume"),
                "pe": val.get("pe"),
                "pb": val.get("pb"),
                "dividend_yield": val.get("dividend_yield"),
            }
        )
    snapshot.sort(key=lambda r: r["code"])
    return snapshot


def append_history(snapshot: list[dict]) -> int:
    """Appends today's compact {date, close, pe, pb, dividend_yield} record per stock."""
    appended = 0
    for row in snapshot:
        if row.get("close") is None:
            continue  # no trade today, nothing to add to the close-price history
        history_store.append_today(
            row["code"],
            {
                "date": row["date"],
                "close": row["close"],
                "pe": row.get("pe"),
                "pb": row.get("pb"),
                "dividend_yield": row.get("dividend_yield"),
            },
        )
        appended += 1
    return appended


def main() -> list[dict]:
    snapshot = fetch_today_snapshot()
    log.info("Fetched today's snapshot for %d stocks", len(snapshot))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT_PATH.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, separators=(",", ":"))
    log.info("Wrote %s", SNAPSHOT_PATH)

    appended = append_history(snapshot)
    log.info("Appended history records for %d stocks", appended)
    return snapshot


if __name__ == "__main__":
    main()
