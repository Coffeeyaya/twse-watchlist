"""Watchlist-only news fetch: Google News RSS, filtered by company name, per ticker.

MOPS material-info announcements (重大訊息) were originally planned too (see plan.md) but turned
out to require a headless browser to query (verified directly against mopsov.twse.com.tw —
plain HTTP POSTs return "no data found" regardless of params). Descoped for v1 — see decisions.md.
This means alerts fired from this data are "new news article mentioning the company," not
"official filing posted." Less precise, but real and scriptable today.
"""

from __future__ import annotations

import hashlib
import logging
import time
from urllib.parse import quote

import feedparser

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RSS_URL = "https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
MAX_ITEMS_PER_STOCK = 5
REQUEST_DELAY_SECONDS = 0.5


def _stable_id(entry) -> str:
    raw = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def fetch_news_for_stock(code: str, company_name: str) -> list[dict]:
    url = RSS_URL.format(query=quote(company_name))
    parsed = feedparser.parse(url)
    items = []
    for entry in parsed.entries[:MAX_ITEMS_PER_STOCK]:
        items.append(
            {
                "id": _stable_id(entry),
                "title": entry.get("title", ""),
                "date": entry.get("published", ""),
                "link": entry.get("link", ""),
                "company_name": company_name,
            }
        )
    return items


def fetch_all(watchlist_codes: list[str], company_names_by_code: dict[str, str]) -> dict[str, list[dict]]:
    news_by_code: dict[str, list[dict]] = {}
    for code in watchlist_codes:
        name = company_names_by_code.get(code, code)
        try:
            news_by_code[code] = fetch_news_for_stock(code, name)
        except Exception:
            log.exception("News fetch failed for %s (%s)", code, name)
            news_by_code[code] = []
        time.sleep(REQUEST_DELAY_SECONDS)
    return news_by_code
