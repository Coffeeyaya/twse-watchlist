"""Descriptive labels for beginners, in Traditional Chinese (per plan.md's language rule — the
primary reader is a non-expert). Every label is descriptive, never prescriptive: this module
must never emit a buy/sell recommendation. See learning.md in the coordination project for the
plain-language explanation of what each of these numbers means.
"""

from __future__ import annotations

from typing import Optional

DISCLAIMER = "本工具僅呈現公開數據與依規則計算的描述性標籤，不構成任何買賣建議，投資決策請自行判斷。"


def percentile_rank(value: Optional[float], series: list[Optional[float]]) -> Optional[float]:
    """% of non-null series values <= value. None if value or the series is empty."""
    if value is None:
        return None
    clean = [v for v in series if v is not None]
    if not clean:
        return None
    n_le = sum(1 for v in clean if v <= value)
    return round(100 * n_le / len(clean), 1)


def _valuation_word(pctl: Optional[float], *, low_is_cheap: bool) -> Optional[str]:
    if pctl is None:
        return None
    if low_is_cheap:
        if pctl <= 20:
            return "相對自身歷史便宜"
        if pctl >= 80:
            return "相對自身歷史昂貴"
        return "相對自身歷史中等水準"
    if pctl >= 80:
        return "殖利率處於自身歷史相對高點"
    if pctl <= 20:
        return "殖利率處於自身歷史相對低點"
    return "殖利率處於自身歷史中等水準"


def valuation_labels(history: list[dict]) -> dict:
    """`history` = a stock's sorted-by-date list of {date, close, pe, pb, dividend_yield}.

    Percentile is computed against whatever history has accumulated so far — NOT always a full
    3-year window right after the backfill (see decisions.md). `lookback_days`/`lookback_start`
    say exactly how much history backs the number, so labels don't silently overclaim.
    """
    if not history:
        return {
            "pe_percentile": None,
            "pb_percentile": None,
            "dividend_yield_percentile": None,
            "pe_label": None,
            "pb_label": None,
            "dividend_yield_label": None,
            "lookback_days": 0,
            "lookback_start_date": None,
        }

    latest = history[-1]
    pe_pctl = percentile_rank(latest.get("pe"), [r.get("pe") for r in history])
    pb_pctl = percentile_rank(latest.get("pb"), [r.get("pb") for r in history])
    yield_pctl = percentile_rank(
        latest.get("dividend_yield"), [r.get("dividend_yield") for r in history]
    )
    return {
        "pe_percentile": pe_pctl,
        "pb_percentile": pb_pctl,
        "dividend_yield_percentile": yield_pctl,
        "pe_label": _valuation_word(pe_pctl, low_is_cheap=True),
        "pb_label": _valuation_word(pb_pctl, low_is_cheap=True),
        "dividend_yield_label": _valuation_word(yield_pctl, low_is_cheap=False),
        "lookback_days": len(history),
        "lookback_start_date": history[0]["date"],
    }


def rsi_label(rsi14: Optional[float]) -> Optional[str]:
    if rsi14 is None:
        return None
    if rsi14 >= 70:
        return "RSI 顯示超買"
    if rsi14 <= 30:
        return "RSI 顯示超賣"
    return "RSI 中性"


_MA_CROSS_LABELS = {
    "golden_cross": "今日出現黃金交叉（20日均線上穿60日均線）",
    "death_cross": "今日出現死亡交叉（20日均線下穿60日均線）",
    "above": "20日均線位於60日均線之上",
    "below": "20日均線位於60日均線之下",
    "insufficient_data": "歷史資料不足，尚無法判斷均線狀態",
}


def ma_cross_label(ma_cross: Optional[dict]) -> Optional[str]:
    if not ma_cross:
        return None
    return _MA_CROSS_LABELS.get(ma_cross.get("state"))


def range_52w_label(range_52w: Optional[dict], *, near_pct: float = 3.0) -> Optional[str]:
    """`near_pct` = how close (%) to the high/low still counts as "near" once today isn't
    itself the extreme. Purely descriptive — a 52-week high is not a sell signal here."""
    if not range_52w:
        return None
    if range_52w.get("window_days", 0) < 60:
        return None
    if range_52w["is_52w_high"]:
        return "股價創52週新高"
    if range_52w["is_52w_low"]:
        return "股價創52週新低"
    if range_52w["pct_from_high"] >= -near_pct:
        return "股價接近52週高點"
    if range_52w["pct_from_low"] <= near_pct:
        return "股價接近52週低點"
    return None


def build_labels(history: list[dict], indicators: dict) -> dict:
    return {
        **valuation_labels(history),
        "rsi_label": rsi_label(indicators.get("rsi14")),
        "ma_cross_label": ma_cross_label(indicators.get("ma_cross")),
        "range_52w_label": range_52w_label(indicators.get("range_52w")),
        "disclaimer": DISCLAIMER,
    }
