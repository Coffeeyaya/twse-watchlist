from labels import (
    DISCLAIMER,
    build_labels,
    ma_cross_label,
    percentile_rank,
    rsi_label,
    valuation_labels,
)


def test_disclaimer_text_is_the_required_wording():
    # This exact wording is a hard requirement (see decisions.md / plan.md): every user-facing
    # output must carry it verbatim. Guards against an accidental edit changing the phrasing.
    assert DISCLAIMER == (
        "本工具僅呈現公開數據與依規則計算的描述性標籤，不構成任何買賣建議，投資決策請自行判斷。"
    )


def test_percentile_rank_none_value_or_empty_series():
    assert percentile_rank(None, [1, 2, 3]) is None
    assert percentile_rank(5, []) is None
    assert percentile_rank(5, [None, None]) is None


def test_percentile_rank_basic():
    assert percentile_rank(3, [1, 2, 3, 4, 5]) == 60.0
    assert percentile_rank(1, [1, 2, 3, 4, 5]) == 20.0
    assert percentile_rank(5, [1, 2, 3, 4, 5]) == 100.0


def test_percentile_rank_ignores_none_entries():
    assert percentile_rank(2, [1, None, 2, None, 3]) == round(100 * 2 / 3, 1)


def test_valuation_labels_empty_history():
    result = valuation_labels([])
    assert result["pe_percentile"] is None
    assert result["pe_label"] is None
    assert result["lookback_days"] == 0
    assert result["lookback_start_date"] is None


def test_valuation_labels_cheap_pe_and_high_yield():
    # 5 days of history, latest day has the lowest PE (cheap) and the highest yield (high).
    history = [
        {"date": "2026-01-01", "pe": 20.0, "pb": 2.0, "dividend_yield": 2.0},
        {"date": "2026-01-02", "pe": 18.0, "pb": 2.0, "dividend_yield": 2.5},
        {"date": "2026-01-03", "pe": 16.0, "pb": 2.0, "dividend_yield": 3.0},
        {"date": "2026-01-04", "pe": 14.0, "pb": 2.0, "dividend_yield": 3.5},
        {"date": "2026-01-05", "pe": 10.0, "pb": 2.0, "dividend_yield": 4.0},
    ]
    result = valuation_labels(history)
    assert result["pe_percentile"] == 20.0
    assert result["pe_label"] == "相對自身歷史便宜"
    assert result["dividend_yield_percentile"] == 100.0
    assert result["dividend_yield_label"] == "殖利率處於自身歷史相對高點"
    assert result["lookback_days"] == 5
    assert result["lookback_start_date"] == "2026-01-01"


def test_rsi_label_boundaries():
    assert rsi_label(None) is None
    assert rsi_label(70.0) == "RSI 顯示超買"
    assert rsi_label(69.9) == "RSI 中性"
    assert rsi_label(30.0) == "RSI 顯示超賣"
    assert rsi_label(30.1) == "RSI 中性"


def test_ma_cross_label_mapping():
    assert ma_cross_label(None) is None
    assert ma_cross_label({"state": "golden_cross"}) == (
        "今日出現黃金交叉（20日均線上穿60日均線）"
    )
    assert ma_cross_label({"state": "death_cross"}) == (
        "今日出現死亡交叉（20日均線下穿60日均線）"
    )
    assert ma_cross_label({"state": "unknown_state"}) is None


def test_build_labels_includes_disclaimer_and_indicator_labels():
    history = [{"date": "2026-01-01", "pe": 10.0, "pb": 1.0, "dividend_yield": 3.0}]
    indicators = {"rsi14": 75.0, "ma_cross": {"state": "above"}}
    result = build_labels(history, indicators)
    assert result["disclaimer"] == DISCLAIMER
    assert result["rsi_label"] == "RSI 顯示超買"
    assert result["ma_cross_label"] == "20日均線位於60日均線之上"
