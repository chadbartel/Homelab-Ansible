"""Pure Python deterministic quantitative analytics (ZERO LLM calls)."""

from __future__ import annotations

import math
from typing import Literal

from trading_lab.domain.models import Bar, TechnicalIndicators
from trading_lab.interfaces.contracts import QuantitativeAnalyzer


class DeterministicQuantitativeAnalyzer(QuantitativeAnalyzer):
    """Computes RSI-14, ATR-14, SMA-20/50, EMA-12/26, 20d volatility, regime, and quant score."""

    MIN_BARS = 50

    def compute_indicators(self, symbol: str, bars: list[Bar]) -> TechnicalIndicators:
        if len(bars) < self.MIN_BARS:
            raise ValueError(
                f"At least {self.MIN_BARS} daily bars are required for {symbol}; got {len(bars)}."
            )

        ordered = sorted(bars, key=lambda b: b.timestamp)
        closes = [float(b.close) for b in ordered]
        highs = [float(b.high) for b in ordered]
        lows = [float(b.low) for b in ordered]

        latest_close = closes[-1]
        rsi_14 = self._wilder_rsi(closes, period=14)
        atr_14 = self._wilder_atr(highs, lows, closes, period=14)
        sma_20 = self._sma(closes, 20)
        sma_50 = self._sma(closes, 50)
        ema_12 = self._ema(closes, 12)
        ema_26 = self._ema(closes, 26)
        volatility_20d = self._annualized_volatility(closes, window=20)
        daily_return_pct = (
            (closes[-1] - closes[-2]) / closes[-2] if closes[-2] > 0 else 0.0
        )
        momentum_20d_pct = (
            (closes[-1] - closes[-21]) / closes[-21]
            if len(closes) >= 21 and closes[-21] > 0
            else 0.0
        )

        trend_regime = self._classify_regime(
            latest_close=latest_close,
            sma_20=sma_20,
            sma_50=sma_50,
            ema_12=ema_12,
            ema_26=ema_26,
        )
        quant_score = self._compute_quant_score(
            rsi_14=rsi_14,
            sma_20=sma_20,
            sma_50=sma_50,
            ema_12=ema_12,
            ema_26=ema_26,
            momentum_20d_pct=momentum_20d_pct,
            volatility_20d=volatility_20d,
        )

        return TechnicalIndicators(
            symbol=symbol.upper(),
            as_of=ordered[-1].timestamp,
            latest_close=round(latest_close, 4),
            rsi_14=round(rsi_14, 4),
            atr_14=round(atr_14, 4),
            sma_20=round(sma_20, 4),
            sma_50=round(sma_50, 4),
            ema_12=round(ema_12, 4),
            ema_26=round(ema_26, 4),
            volatility_20d=round(volatility_20d, 6),
            daily_return_pct=round(daily_return_pct, 6),
            momentum_20d_pct=round(momentum_20d_pct, 6),
            trend_regime=trend_regime,
            quant_score=round(quant_score, 4),
            bars_count=len(ordered),
        )

    @staticmethod
    def _sma(values: list[float], period: int) -> float:
        window = values[-period:]
        return sum(window) / float(period)

    @staticmethod
    def _ema(values: list[float], period: int) -> float:
        multiplier = 2.0 / (period + 1.0)
        ema_val = sum(values[:period]) / float(period)
        for price in values[period:]:
            ema_val = (price - ema_val) * multiplier + ema_val
        return ema_val

    @staticmethod
    def _wilder_rsi(closes: list[float], period: int = 14) -> float:
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(d, 0.0) for d in deltas]
        losses = [max(-d, 0.0) for d in deltas]

        avg_gain = sum(gains[:period]) / float(period)
        avg_loss = sum(losses[:period]) / float(period)

        for idx in range(period, len(deltas)):
            avg_gain = ((avg_gain * (period - 1)) + gains[idx]) / float(period)
            avg_loss = ((avg_loss * (period - 1)) + losses[idx]) / float(period)

        eps = 1e-12
        if avg_gain <= eps and avg_loss <= eps:
            return 50.0
        if avg_loss <= eps:
            return 100.0
        if avg_gain <= eps:
            return 0.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _wilder_atr(
        highs: list[float], lows: list[float], closes: list[float], period: int = 14
    ) -> float:
        true_ranges: list[float] = []
        for idx in range(1, len(closes)):
            prev_close = closes[idx - 1]
            tr = max(
                highs[idx] - lows[idx],
                abs(highs[idx] - prev_close),
                abs(lows[idx] - prev_close),
            )
            true_ranges.append(tr)

        atr = sum(true_ranges[:period]) / float(period)
        for tr in true_ranges[period:]:
            atr = ((atr * (period - 1)) + tr) / float(period)
        return atr

    @staticmethod
    def _annualized_volatility(closes: list[float], window: int = 20) -> float:
        returns: list[float] = []
        slice_closes = closes[-(window + 1) :]
        for idx in range(1, len(slice_closes)):
            prev = slice_closes[idx - 1]
            if prev > 0:
                returns.append((slice_closes[idx] - prev) / prev)
        if len(returns) < 2:
            return 0.0
        mean_ret = sum(returns) / float(len(returns))
        variance = sum((r - mean_ret) ** 2 for r in returns) / float(len(returns) - 1)
        return math.sqrt(max(variance, 0.0)) * math.sqrt(252.0)

    @staticmethod
    def _classify_regime(
        *,
        latest_close: float,
        sma_20: float,
        sma_50: float,
        ema_12: float,
        ema_26: float,
    ) -> Literal["bullish", "bearish", "neutral"]:
        if ema_12 > ema_26 and sma_20 > sma_50 and latest_close >= sma_20:
            return "bullish"
        if ema_12 < ema_26 and sma_20 < sma_50 and latest_close <= sma_20:
            return "bearish"
        return "neutral"

    @staticmethod
    def _compute_quant_score(
        *,
        rsi_14: float,
        sma_20: float,
        sma_50: float,
        ema_12: float,
        ema_26: float,
        momentum_20d_pct: float,
        volatility_20d: float,
    ) -> float:
        ema_signal = ((ema_12 - ema_26) / ema_26) * 10.0 if ema_26 > 0 else 0.0
        sma_signal = ((sma_20 - sma_50) / sma_50) * 8.0 if sma_50 > 0 else 0.0
        mom_signal = momentum_20d_pct * 4.0

        # RSI centered around 50, penalized slightly when deeply overbought (>75).
        if rsi_14 > 75.0:
            rsi_signal = -0.25
        elif rsi_14 < 25.0:
            rsi_signal = 0.25
        else:
            rsi_signal = (rsi_14 - 50.0) / 50.0

        raw = 0.35 * ema_signal + 0.25 * sma_signal + 0.25 * mom_signal + 0.15 * rsi_signal
        # Mild volatility damping so extreme vol reduces conviction.
        vol_damping = 1.0 / (1.0 + max(0.0, volatility_20d - 0.25))
        score = raw * vol_damping
        return max(-1.0, min(1.0, score))
