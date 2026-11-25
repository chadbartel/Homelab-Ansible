"""Market data providers with Alpaca, Yahoo Chart API, and deterministic offline fallback."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from datetime import UTC, datetime, timedelta

import httpx

from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import Bar
from trading_lab.interfaces.contracts import MarketDataProvider

logger = logging.getLogger(__name__)

_DEFAULT_ANCHOR_PRICES: dict[str, float] = {
    "AAPL": 225.0,
    "MSFT": 420.0,
    "NVDA": 135.0,
    "AMZN": 205.0,
    "GOOGL": 175.0,
    "SPY": 585.0,
}


class AlpacaMarketDataProvider(MarketDataProvider):
    """Fetches daily historical OHLCV bars via alpaca-py StockHistoricalDataClient."""

    def __init__(self, api_key: str, secret_key: str) -> None:
        self._api_key = api_key
        self._secret_key = secret_key

    def _fetch_sync(self, symbol: str, limit: int) -> list[Bar]:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(
            api_key=self._api_key,
            secret_key=self._secret_key,
        )
        end = datetime.now(UTC)
        # Calendar days buffer for weekends/holidays.
        start = end - timedelta(days=max(int(limit * 1.8), 120))
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        barset = client.get_stock_bars(req)
        raw_bars = barset.data.get(symbol, []) if hasattr(barset, "data") else barset[symbol]
        bars = [
            Bar(
                symbol=symbol.upper(),
                timestamp=b.timestamp if b.timestamp.tzinfo else b.timestamp.replace(tzinfo=UTC),
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=float(b.volume),
                source="alpaca",
            )
            for b in raw_bars
        ]
        bars.sort(key=lambda item: item.timestamp)
        return bars[-limit:]

    async def get_daily_bars(self, symbol: str, limit: int = 90) -> list[Bar]:
        return await asyncio.to_thread(self._fetch_sync, symbol.upper(), limit)


class YahooChartMarketDataProvider(MarketDataProvider):
    """Fetches public daily OHLCV bars from Yahoo Finance v8 chart JSON endpoint."""

    CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def __init__(
        self,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._transport = transport

    async def get_daily_bars(self, symbol: str, limit: int = 90) -> list[Bar]:
        sym = symbol.upper()
        url = self.CHART_URL.format(symbol=sym)
        params = {"range": "6mo", "interval": "1d"}
        headers = {"User-Agent": "TradingLab/0.1 (+https://github.com/homelab)"}
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
            headers=headers,
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()

        results = payload.get("chart", {}).get("result") or []
        if not results:
            return []
        result = results[0]
        timestamps = result.get("timestamp") or []
        quotes = (result.get("indicators", {}).get("quote") or [{}])[0]
        opens = quotes.get("open") or []
        highs = quotes.get("high") or []
        lows = quotes.get("low") or []
        closes = quotes.get("close") or []
        volumes = quotes.get("volume") or []

        bars: list[Bar] = []
        for idx, ts in enumerate(timestamps):
            if idx >= len(closes) or closes[idx] is None:
                continue
            close_val = float(closes[idx])
            open_val = (
                float(opens[idx])
                if idx < len(opens) and opens[idx] is not None
                else close_val
            )
            high_val = (
                float(highs[idx])
                if idx < len(highs) and highs[idx] is not None
                else max(open_val, close_val)
            )
            low_val = (
                float(lows[idx])
                if idx < len(lows) and lows[idx] is not None
                else min(open_val, close_val)
            )
            vol_val = (
                float(volumes[idx])
                if idx < len(volumes) and volumes[idx] is not None
                else 0.0
            )
            if close_val <= 0:
                continue
            bars.append(
                Bar(
                    symbol=sym,
                    timestamp=datetime.fromtimestamp(int(ts), tz=UTC),
                    open=round(open_val, 4),
                    high=round(max(high_val, open_val, close_val), 4),
                    low=round(min(low_val, open_val, close_val), 4),
                    close=round(close_val, 4),
                    volume=vol_val,
                    source="yahoo_chart",
                )
            )
        bars.sort(key=lambda item: item.timestamp)
        return bars[-limit:]


class SyntheticMarketDataProvider(MarketDataProvider):
    """Deterministic synthetic OHLCV generator ensuring cycles never fail offline."""

    def __init__(self, as_of: datetime | None = None) -> None:
        self._as_of = as_of

    async def get_daily_bars(self, symbol: str, limit: int = 90) -> list[Bar]:
        sym = symbol.upper()
        count = max(limit, 65)
        digest = hashlib.sha256(sym.encode("utf-8")).hexdigest()
        seed = int(digest[:12], 16)
        rng = random.Random(seed)

        base_price = _DEFAULT_ANCHOR_PRICES.get(sym, 100.0 + (seed % 250))
        drift = rng.uniform(-0.0003, 0.0012)
        vol = rng.uniform(0.008, 0.022)

        end_date = (self._as_of or datetime.now(UTC)).replace(
            hour=20, minute=0, second=0, microsecond=0
        )
        # Build business-day timestamps going backwards.
        dates: list[datetime] = []
        cursor = end_date
        while len(dates) < count:
            if cursor.weekday() < 5:
                dates.append(cursor)
            cursor -= timedelta(days=1)
        dates.reverse()

        price = base_price
        bars: list[Bar] = []
        for dt in dates:
            ret = drift + rng.gauss(0.0, vol)
            open_p = price
            close_p = max(1.0, open_p * (1.0 + ret))
            intraday_spread = abs(rng.gauss(0.0, vol * 0.6)) + 0.002
            high_p = max(open_p, close_p) * (1.0 + intraday_spread)
            low_p = max(0.5, min(open_p, close_p) * (1.0 - intraday_spread))
            volume = float(int(rng.uniform(15_000_000, 65_000_000)))
            bars.append(
                Bar(
                    symbol=sym,
                    timestamp=dt,
                    open=round(open_p, 4),
                    high=round(high_p, 4),
                    low=round(low_p, 4),
                    close=round(close_p, 4),
                    volume=volume,
                    source="synthetic_fallback",
                )
            )
            price = close_p
        return bars[-limit:]


class FallbackMarketDataProvider(MarketDataProvider):
    """Tries market data providers in order until one yields >= min_bars daily bars."""

    def __init__(self, providers: list[MarketDataProvider], min_bars: int = 60) -> None:
        self._providers = providers
        self._min_bars = min_bars

    async def get_daily_bars(self, symbol: str, limit: int = 90) -> list[Bar]:
        sym = symbol.upper()
        effective_limit = max(limit, self._min_bars)
        for provider in self._providers:
            try:
                bars = await provider.get_daily_bars(sym, limit=effective_limit)
                if len(bars) >= self._min_bars:
                    return bars[-effective_limit:]
                logger.warning(
                    "Market provider %s returned %d bars (< %d) for %s; trying fallback",
                    provider.__class__.__name__,
                    len(bars),
                    self._min_bars,
                    sym,
                )
            except Exception as exc:
                logger.warning(
                    "Market provider %s failed for %s: %s; trying fallback",
                    provider.__class__.__name__,
                    sym,
                    exc,
                )
        return await SyntheticMarketDataProvider().get_daily_bars(sym, limit=effective_limit)


def build_market_data_provider(settings: TradingLabSettings) -> MarketDataProvider:
    """Construct the market data provider chain based on configuration."""
    chain: list[MarketDataProvider] = []
    if settings.alpaca_configured:
        chain.append(
            AlpacaMarketDataProvider(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
            )
        )
    chain.append(YahooChartMarketDataProvider())
    chain.append(SyntheticMarketDataProvider())
    return FallbackMarketDataProvider(chain, min_bars=60)
