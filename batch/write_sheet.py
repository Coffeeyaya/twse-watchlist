"""Pushes results to the Google Sheet via a service account.

Contract (see decisions.md in the coordination project for the human setup steps this depends
on): env var `GOOGLE_SERVICE_ACCOUNT_JSON` holds the service-account JSON key content (not a file
path — GitHub Actions secrets are strings), `GOOGLE_SHEET_ID` holds the target Sheet's ID (from
its URL). The Sheet must already be shared with the service account's email as Editor.

Tabs (Traditional Chinese — dad reads this directly, per plan.md's language rule):
- "自選清單"（input, user-edited）— column A = ticker code, read but never written by this script.
- "全市場"（output, overwritten每次執行）— every TWSE-listed stock's latest snapshot + labels.
- "自選股詳情"（output, overwritten每次執行）— same columns, filtered to the watchlist only, plus a
  placeholder news column (populated by fetch_watchlist_news.py once that's wired in).

NOT live-tested against a real Sheet — the service account doesn't exist yet (human step, see
decisions.md/track.md). Written against the documented gspread/google-auth API; verify end-to-end
once the account is created.
"""

from __future__ import annotations

import json
import logging
import os

import gspread
from google.oauth2.service_account import Credentials

import labels

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

WATCHLIST_TAB = "自選清單"
FULL_MARKET_TAB = "全市場"
WATCHLIST_DETAIL_TAB = "自選股詳情"

HEADER = ["代號", "名稱", "收盤價", "漲跌", "本益比", "股價淨值比", "殖利率", "RSI(14)", "均線狀態", "估值標籤", "資料日期"]


def _client() -> gspread.Client:
    key_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(key_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def read_watchlist_codes(sheet: gspread.Spreadsheet) -> list[str]:
    try:
        ws = sheet.worksheet(WATCHLIST_TAB)
    except gspread.WorksheetNotFound:
        log.warning("Tab %r not found — treating watchlist as empty", WATCHLIST_TAB)
        return []
    values = ws.col_values(1)[1:]  # skip header row
    return [v.strip() for v in values if v.strip()]


def _row_for(stock: dict) -> list:
    ind = stock.get("indicators", {})
    lbl = stock.get("labels", {})
    valuation_tags = [t for t in (lbl.get("pe_label"), lbl.get("pb_label")) if t]
    return [
        stock["code"],
        stock.get("name") or "",
        stock.get("close"),
        stock.get("change"),
        stock.get("pe"),
        stock.get("pb"),
        stock.get("dividend_yield"),
        ind.get("rsi14"),
        lbl.get("ma_cross_label") or "",
        "、".join(valuation_tags),
        stock.get("date") or "",
    ]


def _overwrite_tab(sheet: gspread.Spreadsheet, tab_name: str, rows: list[list]) -> None:
    try:
        ws = sheet.worksheet(tab_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(rows) + 10, 100), cols=len(HEADER))
    disclaimer_row = [labels.DISCLAIMER]
    ws.update([HEADER] + rows + [disclaimer_row], value_input_option=gspread.utils.ValueInputOption.raw)
    log.info("Wrote %d rows to tab %r (+ disclaimer)", len(rows), tab_name)


def write_dashboard_data(dashboard_data: dict) -> None:
    client = _client()
    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])

    stocks = dashboard_data["stocks"]
    _overwrite_tab(sheet, FULL_MARKET_TAB, [_row_for(s) for s in stocks])

    watchlist_codes = set(read_watchlist_codes(sheet))
    if watchlist_codes:
        watchlist_rows = [_row_for(s) for s in stocks if s["code"] in watchlist_codes]
        _overwrite_tab(sheet, WATCHLIST_DETAIL_TAB, watchlist_rows)
    else:
        log.info("Watchlist is empty — skipping %r", WATCHLIST_DETAIL_TAB)


def main() -> None:
    from pathlib import Path

    dashboard_path = Path(__file__).resolve().parent.parent / "data" / "dashboard.json"
    with dashboard_path.open(encoding="utf-8") as f:
        dashboard_data = json.load(f)
    write_dashboard_data(dashboard_data)


if __name__ == "__main__":
    main()
