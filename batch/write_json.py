"""Builds data/dashboard.json — the single file the static dashboard fetches client-side.

Combines today's snapshot (data/market_snapshot.json, written by fetch_market.py) with each
stock's computed indicators + descriptive labels, derived from its accumulated history
(data/history/<code>.json).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import history_store
import indicators as indicators_mod
import labels as labels_mod

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_PATH = DATA_DIR / "market_snapshot.json"
DASHBOARD_PATH = DATA_DIR / "dashboard.json"


def build_dashboard_data() -> dict:
    with SNAPSHOT_PATH.open(encoding="utf-8") as f:
        snapshot = json.load(f)

    stocks = []
    for row in snapshot:
        code = row["code"]
        history = history_store.load_history(code)
        ind = indicators_mod.compute_indicators(history)
        lbl = labels_mod.build_labels(history, ind)
        change_percent = indicators_mod.compute_change_percent(row.get("close"), row.get("change"))
        stocks.append(
            {
                **row,
                "change_percent": change_percent,
                "indicators": ind,
                "labels": lbl,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": labels_mod.DISCLAIMER,
        "stock_count": len(stocks),
        "stocks": stocks,
    }


def main() -> None:
    data = build_dashboard_data()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DASHBOARD_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log.info("Wrote %s (%d stocks)", DASHBOARD_PATH, data["stock_count"])


if __name__ == "__main__":
    main()
