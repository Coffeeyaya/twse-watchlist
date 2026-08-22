"""Shared HTTP client + normalization for TWSE data sources.

Two families of endpoint are used, both free and keyless:

- openapi.twse.com.tw: bulk, TODAY-ONLY snapshot. Bare JSON array of dicts with English keys.
  Used for the daily incremental fetch.
- www.twse.com.tw (classic): bulk, date-parameterized (accepts any past trading date). Nested
  JSON with Chinese-labeled table rows. Used only for the one-time historical backfill.

Both are normalized here into the same per-stock dict shape so downstream code (indicators.py,
labels.py) never has to know which source a record came from.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

USER_AGENT = "Mozilla/5.0 (compatible; twse-watchlist/1.0; +https://github.com/)"
REQUEST_TIMEOUT = 20

OPENAPI_STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
OPENAPI_BWIBBU_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
CLASSIC_MI_INDEX = "https://www.twse.com.tw/exchangeReport/MI_INDEX"
CLASSIC_BWIBBU_D = "https://www.twse.com.tw/exchangeReport/BWIBBU_d"

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def _get_json(url: str, params: Optional[dict] = None, retries: int = 3, backoff: float = 1.5) -> dict:
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"TWSE request failed after {retries} attempts: {url} {params}") from last_exc


def roc_to_iso(roc_date: str) -> str:
    """'1150821' (ROC year/month/day, 3+2+2 digits) -> '2026-08-21'."""
    roc_date = roc_date.strip()
    year = int(roc_date[:-4]) + 1911
    month = roc_date[-4:-2]
    day = roc_date[-2:]
    return f"{year:04d}-{month}-{day}"


def iso_to_twse_yyyymmdd(iso_date: str) -> str:
    """'2026-08-21' -> '20260821' (format the classic date-parameterized endpoints expect)."""
    return iso_date.replace("-", "")


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip().replace(",", "")
    if value in ("", "--", "-", "N/A"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: Optional[str]) -> Optional[int]:
    f = _to_float(value)
    return int(f) if f is not None else None


# ---------------------------------------------------------------------------
# Daily incremental fetch (openapi.twse.com.tw, today only)
# ---------------------------------------------------------------------------


def fetch_today_ohlc() -> dict[str, dict]:
    """Returns {code: {name, date, open, high, low, close, change, volume, transactions}}."""
    rows = _get_json(OPENAPI_STOCK_DAY_ALL)
    out = {}
    for row in rows:
        code = row.get("Code")
        if not code:
            continue
        close = _to_float(row.get("ClosingPrice"))
        if close is None:
            continue  # suspended / no trade today
        out[code] = {
            "code": code,
            "name": row.get("Name", "").strip(),
            "date": roc_to_iso(row["Date"]),
            "open": _to_float(row.get("OpeningPrice")),
            "high": _to_float(row.get("HighestPrice")),
            "low": _to_float(row.get("LowestPrice")),
            "close": close,
            "change": _to_float(row.get("Change")),
            "volume": _to_int(row.get("TradeVolume")),
            "transactions": _to_int(row.get("Transaction")),
        }
    return out


def fetch_today_valuation() -> dict[str, dict]:
    """Returns {code: {name, date, pe, pb, dividend_yield}}. Only common stocks (no ETFs)."""
    rows = _get_json(OPENAPI_BWIBBU_ALL)
    out = {}
    for row in rows:
        code = row.get("Code")
        if not code:
            continue
        out[code] = {
            "code": code,
            "name": row.get("Name", "").strip(),
            "date": roc_to_iso(row["Date"]),
            "pe": _to_float(row.get("PEratio")),
            "pb": _to_float(row.get("PBratio")),
            "dividend_yield": _to_float(row.get("DividendYield")),
        }
    return out


# ---------------------------------------------------------------------------
# Historical backfill (classic www.twse.com.tw, date-parameterized)
# ---------------------------------------------------------------------------


def fetch_historical_ohlc(iso_date: str) -> dict[str, dict]:
    """One past trading day's full-market OHLC. Empty dict on weekends/holidays (no data)."""
    payload = _get_json(
        CLASSIC_MI_INDEX,
        params={"response": "json", "date": iso_to_twse_yyyymmdd(iso_date), "type": "ALL"},
    )
    if payload.get("stat") != "OK":
        return {}
    table = _find_table(payload, name_hint="每日收盤行情")
    if table is None:
        return {}
    out = {}
    for row in table:
        if len(row) < 9:
            continue
        code = row[0].strip()
        close = _to_float(row[8])
        if not code or close is None:
            continue
        out[code] = {
            "code": code,
            "name": row[1].strip(),
            "date": iso_date,
            "close": close,
        }
    return out


def fetch_historical_valuation(iso_date: str) -> dict[str, dict]:
    """One past trading day's full-market P/E, P/B, dividend yield (common stocks only)."""
    payload = _get_json(
        CLASSIC_BWIBBU_D,
        params={"response": "json", "date": iso_to_twse_yyyymmdd(iso_date), "selectType": "ALL"},
    )
    if payload.get("stat") != "OK":
        return {}
    table = payload.get("data")
    if not table:
        return {}
    # Columns: 證券代號, 證券名稱, 收盤價, 殖利率(%), 股利年度, 本益比, 股價淨值比, 財報年/季
    out = {}
    for row in table:
        if len(row) < 7:
            continue
        code = row[0].strip()
        if not code:
            continue
        out[code] = {
            "code": code,
            "name": row[1].strip(),
            "date": iso_date,
            "dividend_yield": _to_float(row[3]),
            "pe": _to_float(row[5]),
            "pb": _to_float(row[6]),
        }
    return out


def _find_table(payload: dict, name_hint: str) -> Optional[list]:
    """MI_INDEX bundles several tables in `payload["tables"]`; find the one we want by title
    (confirmed shape, tested live across 2014-2026 — see decisions.md)."""
    for table in payload.get("tables", []):
        if name_hint in table.get("title", ""):
            return table.get("data")
    return None
