"""Daily orchestrator, run by .github/workflows/daily.yml.

Runs the full-market pipeline unconditionally (needs no external account setup). Google Sheet
output and LINE alerts are skipped gracefully — with a clear log line, not a crash — if their
required env vars aren't set yet, since both depend on human setup steps that may not be done yet
(see decisions.md in the coordination project). The static dashboard (data/*.json) always gets
written regardless.
"""

from __future__ import annotations

import logging
import os

import fetch_market
import history_store
import write_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _sheets_configured() -> bool:
    return bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")) and bool(
        os.environ.get("GOOGLE_SHEET_ID")
    )


def _line_configured() -> bool:
    return bool(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")) and bool(
        os.environ.get("LINE_RECIPIENT_USER_IDS")
    )


def main() -> None:
    log.info("=== Daily batch starting ===")

    fetch_market.main()
    dashboard_data = write_json.build_dashboard_data()
    import json
    from pathlib import Path

    dashboard_path = Path(__file__).resolve().parent.parent / "data" / "dashboard.json"
    with dashboard_path.open("w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, separators=(",", ":"))
    log.info("Dashboard data written (%d stocks)", dashboard_data["stock_count"])

    if not _sheets_configured():
        log.warning(
            "GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SHEET_ID not set — skipping Sheet output "
            "and watchlist-dependent alerts (human setup step, see decisions.md)"
        )
        log.info("=== Daily batch done (data + dashboard only) ===")
        return

    import write_sheet

    write_sheet.write_dashboard_data(dashboard_data)

    client = write_sheet._client()
    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    watchlist_codes = write_sheet.read_watchlist_codes(sheet)

    if not watchlist_codes:
        log.info("Watchlist is empty — nothing to alert on")
        log.info("=== Daily batch done ===")
        return

    stocks_by_code = {s["code"]: s for s in dashboard_data["stocks"]}

    news_by_code = {}
    try:
        import fetch_watchlist_news

        names = {code: stocks_by_code[code]["name"] for code in watchlist_codes if code in stocks_by_code}
        news_by_code = fetch_watchlist_news.fetch_all(watchlist_codes, names)
    except Exception:
        log.exception("fetch_watchlist_news failed — continuing without news alerts")

    write_sheet.write_watchlist_news(sheet, news_by_code)

    if not _line_configured():
        log.warning(
            "LINE_CHANNEL_ACCESS_TOKEN / LINE_RECIPIENT_USER_IDS not set — skipping alerts "
            "(human setup step, see decisions.md)"
        )
        log.info("=== Daily batch done (no alerts) ===")
        return

    import alerts

    history_by_code = {code: history_store.load_history(code) for code in watchlist_codes}
    alerts.run(watchlist_codes, stocks_by_code, history_by_code, news_by_code)

    log.info("=== Daily batch done ===")


if __name__ == "__main__":
    main()
