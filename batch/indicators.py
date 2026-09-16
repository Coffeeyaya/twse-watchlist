"""Technical indicators computed from a stock's close-price history.

All functions degrade gracefully (return None / "insufficient_data") when there isn't enough
history yet, rather than raising or silently computing over too-short a window — history is still
accumulating for most stocks right after the backfill (see decisions.md).
"""

from __future__ import annotations

from typing import Optional


def compute_sma(closes: list[float], window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return round(sum(closes[-window:]) / window, 4)


def compute_rsi(closes: list[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [c if c > 0 else 0.0 for c in changes]
    losses = [-c if c < 0 else 0.0 for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _ema(values: list[float], span: int) -> list[float]:
    """EMA seeded with the SMA of the first `span` values. Output is aligned to the END of the
    input (out[0] corresponds to values[span-1]), i.e. shorter than `values` by span-1."""
    k = 2 / (span + 1)
    ema = sum(values[:span]) / span
    out = [ema]
    for v in values[span:]:
        ema = v * k + ema * (1 - k)
        out.append(ema)
    return out


def compute_macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Optional[dict]:
    if len(closes) < slow + signal:
        return None
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    offset = slow - fast  # ema_slow starts `offset` closes later than ema_fast
    macd_line = [f - s for f, s in zip(ema_fast[offset:], ema_slow)]
    if len(macd_line) < signal:
        return None
    signal_line = _ema(macd_line, signal)
    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    return {
        "macd": round(macd_val, 4),
        "signal": round(signal_val, 4),
        "histogram": round(macd_val - signal_val, 4),
    }


def compute_stochastic(history: list[dict], period: int = 9) -> Optional[dict]:
    """Stochastic oscillator (KD), Taiwan-brokerage convention: raw %K (RSV) over a `period`-day
    high/low range, then K/D smoothed with a 2/3-1/3 weighted moving average seeded at 50 — the
    method taught in Taiwan retail technical-analysis material, distinct from the plain
    SMA-of-RSV method used elsewhere. Needs `high`/`low` in history records (added alongside
    `volume`); records missing either are skipped, so this returns `None` until `period` days of
    high/low-bearing history have accumulated after this ships (same ramp-up as
    compute_volume_ratio for `volume`).
    """
    triples = [
        (r["high"], r["low"], r["close"])
        for r in history
        if r.get("high") is not None and r.get("low") is not None and r.get("close") is not None
    ]
    if len(triples) < period:
        return None

    k = d = 50.0
    k_prev = d_prev = None
    for i in range(period - 1, len(triples)):
        window = triples[i - period + 1 : i + 1]
        highest = max(h for h, _, _ in window)
        lowest = min(l for _, l, _ in window)
        close = triples[i][2]
        rsv = 50.0 if highest == lowest else (close - lowest) / (highest - lowest) * 100
        k_prev, d_prev = k, d
        k = (2 / 3) * k + (1 / 3) * rsv
        d = (2 / 3) * d + (1 / 3) * k

    state = "overbought" if k >= 80 else "oversold" if k <= 20 else "neutral"
    cross = None
    crossed_today = False
    if k_prev is not None:
        prev_diff = k_prev - d_prev
        today_diff = k - d
        if prev_diff <= 0 < today_diff:
            cross, crossed_today = "golden_cross", True
        elif prev_diff >= 0 > today_diff:
            cross, crossed_today = "death_cross", True

    return {
        "k": round(k, 2),
        "d": round(d, 2),
        "state": state,
        "cross": cross,
        "crossed_today": crossed_today,
    }


def compute_ma_cross(closes: list[float], short: int = 20, long: int = 60) -> dict:
    if len(closes) < long:
        return {"state": "insufficient_data", "crossed_today": False}

    short_series = [
        sum(closes[i - short + 1 : i + 1]) / short for i in range(short - 1, len(closes))
    ]
    long_series = [
        sum(closes[i - long + 1 : i + 1]) / long for i in range(long - 1, len(closes))
    ]
    offset = long - short  # short_series starts `offset` closes earlier than long_series
    diffs = [s - l for s, l in zip(short_series[offset:], long_series)]

    if len(diffs) < 2:
        return {"state": "above" if diffs[-1] > 0 else "below", "crossed_today": False}

    today, yesterday = diffs[-1], diffs[-2]
    if yesterday <= 0 < today:
        return {"state": "golden_cross", "crossed_today": True}
    if yesterday >= 0 > today:
        return {"state": "death_cross", "crossed_today": True}
    return {"state": "above" if today > 0 else "below", "crossed_today": False}


def compute_indicators(history: list[dict]) -> dict:
    """`history` = a stock's sorted-by-date list of {date, close, pe, pb, dividend_yield}."""
    closes = [r["close"] for r in history if r.get("close") is not None]
    return {
        "data_points": len(closes),
        "sma20": compute_sma(closes, 20),
        "sma60": compute_sma(closes, 60),
        "rsi14": compute_rsi(closes, 14),
        "macd": compute_macd(closes),
        "ma_cross": compute_ma_cross(closes),
        "kd": compute_stochastic(history),
    }
