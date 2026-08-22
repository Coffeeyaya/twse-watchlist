# twse-watchlist

Daily screening + research dashboard for Taiwan-listed (TWSE, 上市) stocks. Not a portfolio
tracker and not investment advice — it computes descriptive labels (e.g. "cheap relative to its
own 3-year history", "RSI indicates oversold") from public data so two non-expert readers (family)
can do their own research. See the design doc for full rationale: it lives in the sibling
coordination project, not in this repo — see "Design & coordination" below.

## Design & coordination

This repo holds code + data only. The design doc, decision log, and status tracker live in a
separate local coordination project (`~/Desktop/improvisation/finance/`, not itself published),
following the collaboration protocol at `~/Desktop/CSLAB/collaboration.md`:

- `concepts/plan.md` — architecture, scope, why.
- `concepts/learning.md` — plain-language notes on RSI/MA/P-E/P-B for a non-expert reader.
- `status/track.md` — current build status.
- `status/decisions.md` — judgment calls and their defaults.

## Layout

```
batch/                   Python job, runs daily via GitHub Actions
├── fetch_market.py       TWSE OpenAPI: STOCK_DAY_ALL + BWIBBU_ALL (all TWSE-listed stocks, no key)
├── fetch_watchlist_news.py   Google News RSS, watchlist tickers only (MOPS announcements were
│                              descoped from v1 — needs a headless browser, see decisions.md)
├── indicators.py          SMA20/60, MA cross, RSI14, MACD
├── labels.py              Percentile-based valuation labels, RSI-band labels
├── alerts.py              Evaluates trigger rules, pushes via LINE Messaging API
├── write_sheet.py         Pushes results to Google Sheet via service account
└── write_json.py          Writes static /data/*.json for the dashboard

data/                     Committed JSON snapshots (full-market + watchlist detail)
dashboard/                Static HTML/CSS/JS (no build step), Chart.js, served by GitHub Pages
.github/workflows/        daily.yml — cron, ~16:00 Asia/Taipei on trading days
```

## Disclaimer

This tool surfaces public data and computed descriptive labels. It does not give buy/sell
recommendations and knows nothing about your financial situation. Every output surface repeats
this.

## Status

Under active development. See the coordination project's `status/track.md` for current progress.
