"""Shared pytest fixtures for Trading Lab unit and integration tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from trading_lab.analytics.quantitative import DeterministicQuantitativeAnalyzer
from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import (
    Bar,
    HeuristicWeights,
    NewsArticle,
    PortfolioSnapshot,
    TechnicalIndicators,
    TradeAction,
    TradeThesis,
)
from trading_lab.execution.broker import VirtualLedgerBrokerExecutor
from trading_lab.llm.ollama_engine import OllamaThesisEngine
from trading_lab.persistence.repository import TimescaleTradeLedgerRepository
from trading_lab.providers.market_data import SyntheticMarketDataProvider
from trading_lab.providers.news import SyntheticNewsProvider
from trading_lab.risk.gate import DeterministicRiskGate
from trading_lab.services.pipeline import TradingPipelineOrchestrator
from trading_lab.services.reflection import WeeklyReflectionService
from trading_lab.web.app import create_app


def make_bars(
    symbol: str,
    closes: list[float],
    *,
    spread_pct: float = 0.01,
    start_dt: datetime | None = None,
) -> list[Bar]:
    """Generate deterministic ascending daily OHLCV bars from a list of close prices."""
    base = start_dt or (datetime(2026, 1, 2, 20, 0, tzinfo=UTC))
    bars: list[Bar] = []
    for idx, close in enumerate(closes):
        open_p = closes[idx - 1] if idx > 0 else close
        high_p = max(open_p, close) * (1.0 + spread_pct)
        low_p = min(open_p, close) * (1.0 - spread_pct)
        bars.append(
            Bar(
                symbol=symbol.upper(),
                timestamp=base + timedelta(days=idx),
                open=round(open_p, 4),
                high=round(high_p, 4),
                low=round(low_p, 4),
                close=round(close, 4),
                volume=10_000_000.0 + idx * 1000.0,
                source="test_fixture",
            )
        )
    return bars


@pytest.fixture()
def settings(tmp_path: Path) -> TradingLabSettings:
    """Isolated settings backed by in-memory SQLite and temp directories."""
    return TradingLabSettings(
        database_url="sqlite:///:memory:",
        ollama_base_url="http://mock-ollama:11434",
        ollama_model="huihui_ai/qwen3-abliterated:8b-v2",
        ollama_timeout_seconds=10.0,
        alpaca_api_key="",
        alpaca_secret_key="",
        paper_only=True,
        ticker_allowlist="AAPL,MSFT,NVDA,SPY",
        benchmark_symbol="SPY",
        max_position_pct=0.05,
        default_stop_loss_pct=0.03,
        min_stop_loss_pct=0.005,
        max_stop_loss_pct=0.15,
        min_confidence=0.55,
        daily_drawdown_limit_pct=0.03,
        initial_cash=100000.0,
        scheduler_enabled=False,
        log_dir=str(tmp_path / "logs"),
        artifacts_dir=str(tmp_path / "artifacts"),
    )


@pytest.fixture()
def repo(settings: TradingLabSettings) -> TimescaleTradeLedgerRepository:
    """Initialized in-memory SQLite ledger repository."""
    repository = TimescaleTradeLedgerRepository(settings.database_url)
    repository.init_schema()
    return repository


@pytest.fixture()
def sample_indicators() -> TechnicalIndicators:
    return TechnicalIndicators(
        symbol="AAPL",
        as_of=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        latest_close=200.0,
        rsi_14=58.5,
        atr_14=3.25,
        sma_20=195.0,
        sma_50=188.0,
        ema_12=197.5,
        ema_26=193.0,
        volatility_20d=0.22,
        daily_return_pct=0.012,
        momentum_20d_pct=0.045,
        trend_regime="bullish",
        quant_score=0.42,
        bars_count=90,
    )


@pytest.fixture()
def sample_news() -> list[NewsArticle]:
    return [
        NewsArticle(
            symbol="AAPL",
            title="Apple expands enterprise AI services adoption",
            summary="Strong recurring services revenue growth reported.",
            source="test_rss",
            published_at=datetime(2026, 6, 1, 15, 0, tzinfo=UTC),
        )
    ]


@pytest.fixture()
def sample_heuristics() -> HeuristicWeights:
    return HeuristicWeights(version=1)


@pytest.fixture()
def sample_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        timestamp=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        equity=100000.0,
        cash=100000.0,
        positions_value=0.0,
        daily_return_pct=0.0,
        daily_drawdown_pct=0.0,
        spy_price=580.0,
        spy_benchmark_equity=100000.0,
        alpha_vs_spy_pct=0.0,
        broker_mode="virtual_ledger",
    )


def make_thesis(
    *,
    symbol: str = "AAPL",
    action: TradeAction = TradeAction.BUY,
    confidence: float = 0.80,
    target_position_pct: float = 0.04,
    stop_loss_pct: float | None = 0.03,
) -> TradeThesis:
    return TradeThesis(
        symbol=symbol,
        action=action,
        confidence=confidence,
        sentiment_score=0.6,
        target_position_pct=target_position_pct,
        stop_loss_pct=stop_loss_pct,
        catalyst_summary="Strong technical trend and positive catalyst.",
        rationale="EMA-12 above EMA-26 with healthy RSI and volume.",
        model_name="huihui_ai/qwen3-abliterated:8b-v2",
        heuristics_version=1,
    )


def make_mock_ollama_transport(
    chat_handler,
    models: list[str] | None = None,
) -> httpx.MockTransport:
    """Create an httpx.MockTransport servicing /api/chat and /api/tags."""
    installed = models or ["huihui_ai/qwen3-abliterated:8b-v2"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/tags"):
            return httpx.Response(
                200,
                json={"models": [{"name": m} for m in installed]},
            )
        if request.url.path.endswith("/api/chat"):
            body: dict[str, Any] = json.loads(request.content.decode("utf-8"))
            return chat_handler(body)
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


@pytest.fixture()
def test_client(
    settings: TradingLabSettings,
    repo: TimescaleTradeLedgerRepository,
):
    """FastAPI TestClient wired to synthetic providers and a deterministic mock Ollama."""

    def chat_handler(body: dict[str, Any]) -> httpx.Response:
        user_msg = json.loads(body["messages"][-1]["content"])
        if "window_days" in user_msg:
            content = json.dumps(
                {
                    "summary": "Portfolio stayed disciplined against SPY.",
                    "lessons_learned": ["Tight stops preserved capital."],
                    "notes": "Slightly boost trend weight.",
                    "suggested_weights": {
                        "momentum_weight": 0.30,
                        "trend_weight": 0.30,
                        "mean_reversion_weight": 0.15,
                        "news_sentiment_weight": 0.15,
                        "volatility_penalty_weight": 0.10,
                    },
                }
            )
        else:
            sym = user_msg.get("symbol", "AAPL")
            if sym == "AAPL":
                payload = {
                    "action": "BUY",
                    "confidence": 0.82,
                    "sentiment_score": 0.65,
                    "target_position_pct": 0.04,
                    "stop_loss_pct": 0.03,
                    "catalyst_summary": "Positive momentum and services growth.",
                    "rationale": "Favorable deterministic quant profile.",
                }
            elif sym == "NVDA":
                # Deliberately oversized (> 5%) to verify RiskGate rejection end-to-end.
                payload = {
                    "action": "BUY",
                    "confidence": 0.85,
                    "sentiment_score": 0.70,
                    "target_position_pct": 0.09,
                    "stop_loss_pct": 0.03,
                    "catalyst_summary": "High conviction AI demand.",
                    "rationale": "Oversized request should be rejected by RiskGate.",
                }
            else:
                payload = {
                    "action": "HOLD",
                    "confidence": 0.60,
                    "sentiment_score": 0.10,
                    "target_position_pct": 0.0,
                    "stop_loss_pct": 0.03,
                    "catalyst_summary": "Neutral setup.",
                    "rationale": "Await clearer signal.",
                }
            content = json.dumps(payload)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    transport = make_mock_ollama_transport(chat_handler)
    llm = OllamaThesisEngine(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
        transport=transport,
    )
    broker = VirtualLedgerBrokerExecutor(
        repository=repo,
        initial_cash=settings.initial_cash,
        paper_only=settings.paper_only,
    )
    reflection = WeeklyReflectionService(settings=settings, repository=repo, llm_engine=llm)
    orchestrator = TradingPipelineOrchestrator(
        settings=settings,
        market_data=SyntheticMarketDataProvider(),
        news_provider=SyntheticNewsProvider(),
        quant_analyzer=DeterministicQuantitativeAnalyzer(),
        llm_engine=llm,
        risk_gate=DeterministicRiskGate(settings),
        broker=broker,
        repository=repo,
        reflection_service=reflection,
    )
    app = create_app(
        settings=settings,
        repository=repo,
        orchestrator=orchestrator,
        llm_engine=llm,
    )
    with TestClient(app) as client:
        yield client
