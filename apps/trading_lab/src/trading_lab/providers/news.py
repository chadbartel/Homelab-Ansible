"""News providers supporting Alpaca News API, RSS feeds, and offline deterministic fallback."""

from __future__ import annotations

import asyncio
import logging
from calendar import timegm
from datetime import UTC, datetime

import feedparser
import httpx

from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import NewsArticle
from trading_lab.interfaces.contracts import NewsProvider

logger = logging.getLogger(__name__)


class AlpacaNewsProvider(NewsProvider):
    """Fetches symbol-specific news headlines via alpaca-py NewsClient."""

    def __init__(self, api_key: str, secret_key: str) -> None:
        self._api_key = api_key
        self._secret_key = secret_key

    def _fetch_sync(self, symbol: str, limit: int) -> list[NewsArticle]:
        from alpaca.data.historical.news import NewsClient
        from alpaca.data.requests import NewsRequest

        client = NewsClient(api_key=self._api_key, secret_key=self._secret_key)
        req = NewsRequest(symbols=symbol.upper(), limit=limit)
        response = client.get_news(req)
        raw_items = getattr(response, "data", {}).get("news", [])
        articles: list[NewsArticle] = []
        for item in raw_items[:limit]:
            published = getattr(item, "created_at", None) or datetime.now(UTC)
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            articles.append(
                NewsArticle(
                    symbol=symbol.upper(),
                    title=str(getattr(item, "headline", "")).strip(),
                    summary=str(getattr(item, "summary", "") or "").strip(),
                    source=str(getattr(item, "source", "alpaca_news")),
                    url=str(getattr(item, "url", "") or ""),
                    published_at=published,
                )
            )
        return [a for a in articles if a.title]

    async def get_recent_news(self, symbol: str, limit: int = 5) -> list[NewsArticle]:
        return await asyncio.to_thread(self._fetch_sync, symbol.upper(), limit)


class RSSNewsProvider(NewsProvider):
    """Fetches recent headlines from Yahoo Finance & CNBC RSS feeds."""

    YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    CNBC_RSS = "https://www.cnbc.com/id/100003114/device/rss/rss.html"

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._transport = transport

    async def _fetch_feed(self, client: httpx.AsyncClient, url: str) -> list[dict]:
        resp = await client.get(url)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
        return list(parsed.entries or [])

    async def get_recent_news(self, symbol: str, limit: int = 5) -> list[NewsArticle]:
        sym = symbol.upper()
        headers = {"User-Agent": "TradingLab/0.1 (+https://github.com/homelab)"}
        urls = [self.YAHOO_RSS.format(symbol=sym), self.CNBC_RSS]
        articles: list[NewsArticle] = []

        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
            headers=headers,
            follow_redirects=True,
        ) as client:
            for url in urls:
                if len(articles) >= limit:
                    break
                try:
                    entries = await self._fetch_feed(client, url)
                except Exception as exc:
                    logger.debug("RSS fetch failed for %s (%s): %s", sym, url, exc)
                    continue
                for entry in entries:
                    if len(articles) >= limit:
                        break
                    title = str(entry.get("title", "")).strip()
                    if not title:
                        continue
                    published_parsed = entry.get("published_parsed")
                    if published_parsed:
                        published = datetime.fromtimestamp(timegm(published_parsed), tz=UTC)
                    else:
                        published = datetime.now(UTC)
                    articles.append(
                        NewsArticle(
                            symbol=sym,
                            title=title,
                            summary=str(entry.get("summary", "")).strip()[:400],
                            source="rss_yahoo" if "yahoo" in url else "rss_cnbc",
                            url=str(entry.get("link", "")),
                            published_at=published,
                        )
                    )
        return articles[:limit]


class SyntheticNewsProvider(NewsProvider):
    """Deterministic neutral fallback headlines when external feeds are offline."""

    async def get_recent_news(self, symbol: str, limit: int = 5) -> list[NewsArticle]:
        sym = symbol.upper()
        now = datetime.now(UTC)
        templates = [
            (
                f"{sym} trades in line with broader US equities amid steady institutional volume",
                (
                    "Offline neutral fallback headline; rely primarily on deterministic "
                    "technical indicators."
                ),
            ),
            (
                f"Market participants monitor macro data and earnings trajectory for {sym}",
                "No breaking catalyst detected from external feeds; conservative sizing advised.",
            ),
        ]
        return [
            NewsArticle(
                symbol=sym,
                title=title,
                summary=summary,
                source="synthetic_fallback",
                url="",
                published_at=now,
            )
            for title, summary in templates[:limit]
        ]


class FallbackNewsProvider(NewsProvider):
    """Chains configured news providers with deterministic offline fallback."""

    def __init__(self, providers: list[NewsProvider]) -> None:
        self._providers = providers

    async def get_recent_news(self, symbol: str, limit: int = 5) -> list[NewsArticle]:
        sym = symbol.upper()
        for provider in self._providers:
            try:
                items = await provider.get_recent_news(sym, limit=limit)
                if items:
                    return items[:limit]
            except Exception as exc:
                logger.warning(
                    "News provider %s failed for %s: %s; trying fallback",
                    provider.__class__.__name__,
                    sym,
                    exc,
                )
        return await SyntheticNewsProvider().get_recent_news(sym, limit=limit)


def build_news_provider(settings: TradingLabSettings) -> NewsProvider:
    """Construct the news provider chain based on configuration."""
    chain: list[NewsProvider] = []
    if settings.alpaca_configured:
        chain.append(
            AlpacaNewsProvider(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
            )
        )
    chain.append(RSSNewsProvider())
    chain.append(SyntheticNewsProvider())
    return FallbackNewsProvider(chain)
