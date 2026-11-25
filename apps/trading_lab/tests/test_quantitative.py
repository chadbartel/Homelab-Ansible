"""Unit tests for pure Python DeterministicQuantitativeAnalyzer."""

from __future__ import annotations

import math

import pytest

from tests.conftest import make_bars
from trading_lab.analytics.quantitative import DeterministicQuantitativeAnalyzer


def test_uptrend_indicators_all_gains() -> None:
    analyzer = DeterministicQuantitativeAnalyzer()
    closes = [100.0 + i * 1.5 for i in range(60)]
    bars = make_bars("AAPL", closes, spread_pct=0.01)

    ind = analyzer.compute_indicators("AAPL", bars)

    assert ind.symbol == "AAPL"
    assert ind.bars_count == 60
    assert ind.latest_close == pytest.approx(closes[-1], abs=1e-4)
    assert ind.rsi_14 == pytest.approx(100.0, abs=1e-4)
    assert ind.atr_14 > 0.0
    assert ind.sma_20 == pytest.approx(sum(closes[-20:]) / 20.0, abs=1e-4)
    assert ind.sma_50 == pytest.approx(sum(closes[-50:]) / 50.0, abs=1e-4)
    assert ind.sma_20 > ind.sma_50
    assert ind.ema_12 > ind.ema_26
    assert ind.trend_regime == "bullish"
    assert ind.momentum_20d_pct > 0.0
    assert 0.0 < ind.quant_score <= 1.0


def test_downtrend_indicators_all_losses() -> None:
    analyzer = DeterministicQuantitativeAnalyzer()
    closes = [250.0 - i * 1.2 for i in range(60)]
    bars = make_bars("NVDA", closes, spread_pct=0.015)

    ind = analyzer.compute_indicators("NVDA", bars)

    assert ind.rsi_14 == pytest.approx(0.0, abs=1e-4)
    assert ind.sma_20 < ind.sma_50
    assert ind.ema_12 < ind.ema_26
    assert ind.trend_regime == "bearish"
    assert ind.momentum_20d_pct < 0.0
    assert -1.0 <= ind.quant_score < 0.0


def test_flat_prices_edge_case() -> None:
    analyzer = DeterministicQuantitativeAnalyzer()
    closes = [150.0] * 60
    bars = make_bars("SPY", closes, spread_pct=0.0)

    ind = analyzer.compute_indicators("SPY", bars)

    assert ind.rsi_14 == pytest.approx(50.0, abs=1e-4)
    assert ind.atr_14 == pytest.approx(0.0, abs=1e-4)
    assert ind.sma_20 == pytest.approx(150.0, abs=1e-4)
    assert ind.sma_50 == pytest.approx(150.0, abs=1e-4)
    assert ind.ema_12 == pytest.approx(150.0, abs=1e-4)
    assert ind.ema_26 == pytest.approx(150.0, abs=1e-4)
    assert ind.volatility_20d == pytest.approx(0.0, abs=1e-6)
    assert ind.daily_return_pct == pytest.approx(0.0, abs=1e-6)
    assert ind.trend_regime == "neutral"


def test_oscillating_series_and_unsorted_input() -> None:
    analyzer = DeterministicQuantitativeAnalyzer()
    closes = [100.0 + 5.0 * math.sin(i * 0.4) + 0.1 * i for i in range(70)]
    bars = make_bars("MSFT", closes, spread_pct=0.01)

    ind_ordered = analyzer.compute_indicators("MSFT", bars)
    ind_reversed = analyzer.compute_indicators("MSFT", list(reversed(bars)))

    assert ind_ordered.model_dump() == ind_reversed.model_dump()
    assert 0.0 < ind_ordered.rsi_14 < 100.0
    assert ind_ordered.volatility_20d > 0.0
    assert ind_ordered.atr_14 > 0.0
    assert -1.0 <= ind_ordered.quant_score <= 1.0


def test_insufficient_bars_raises_value_error() -> None:
    analyzer = DeterministicQuantitativeAnalyzer()
    bars = make_bars("AAPL", [100.0 + i for i in range(49)])

    with pytest.raises(ValueError, match="At least 50 daily bars"):
        analyzer.compute_indicators("AAPL", bars)
