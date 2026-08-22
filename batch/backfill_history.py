"""One-time (or resumable) historical backfill: walks back N years of trading days via the
classic date-parameterized TWSE endpoints and populates data/history/<code>.json.

NOT part of the daily cron — run manually or via a workflow_dispatch job once, before the daily
incremental job (fetch_market.py) takes over. Safe to re-run: skips dates already present in a
stock's history file, so an interrupted run can resume where it left off.

Usage:
    python batch/backfill_history.py [--years 3] [--delay 1.0] [--start-date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date, timedelta

import history_store
import twse_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def trading_day_candidates(start: date, end: date):
    """Every calendar day Mon-Fri in [start, end]. TWSE holidays are filtered out downstream by
    the endpoint itself returning stat != 'OK' for non-trading days."""
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            yield d
        d += timedelta(days=1)


def already_covered(existing_dates: set[str], iso_date: str) -> bool:
    return iso_date in existing_dates


def run(years: int, delay: float, start_date: str | None) -> None:
    end = date.today() - timedelta(days=1)  # yesterday; today comes from fetch_market.py
    start = date.fromisoformat(start_date) if start_date else end - timedelta(days=365 * years)

    log.info("Backfilling %s to %s (%d candidate weekdays)", start, end, (end - start).days)

    history_cache: dict[str, list[dict]] = {}
    dates_seen_per_code: dict[str, set[str]] = {}

    days = list(trading_day_candidates(start, end))
    for i, d in enumerate(days):
        iso = d.isoformat()
        ohlc = twse_client.fetch_historical_ohlc(iso)
        time.sleep(delay)
        valuation = twse_client.fetch_historical_valuation(iso)
        time.sleep(delay)

        if not valuation:
            log.info("[%d/%d] %s: no data (holiday), skipping", i + 1, len(days), iso)
            continue

        added = 0
        for code, val in valuation.items():
            close = ohlc.get(code, {}).get("close")
            if close is None:
                continue
            record = {
                "date": iso,
                "close": close,
                "pe": val.get("pe"),
                "pb": val.get("pb"),
                "dividend_yield": val.get("dividend_yield"),
            }
            history_cache.setdefault(code, [])
            dates_seen_per_code.setdefault(code, set())
            if iso not in dates_seen_per_code[code]:
                history_cache[code].append(record)
                dates_seen_per_code[code].add(iso)
                added += 1
        log.info("[%d/%d] %s: %d stocks", i + 1, len(days), iso, added)

        # Flush periodically so an interrupted run doesn't lose everything.
        if (i + 1) % 60 == 0:
            _flush(history_cache)
            history_cache.clear()

    _flush(history_cache)
    log.info("Backfill complete.")


def _flush(history_cache: dict[str, list[dict]]) -> None:
    for code, new_records in history_cache.items():
        existing = history_store.load_history(code)
        merged = history_store.merge_records(existing, new_records)
        history_store.save_history(code, merged)
    if history_cache:
        log.info("Flushed history for %d stocks", len(history_cache))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--start-date", type=str, default=None, help="override: YYYY-MM-DD")
    args = parser.parse_args()
    run(args.years, args.delay, args.start_date)
