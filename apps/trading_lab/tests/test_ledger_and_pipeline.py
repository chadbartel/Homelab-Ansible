"""Integration tests for repository, broker, reflection, pipeline, FastAPI, and scheduler."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.conftest import make_bars, make_mock_ollama_transport
from trading_lab.analytics.quantitative import DeterministicQuantitativeAnalyzer
from trading_lab.domain.models import (
    OrderRequest,
    PortfolioSnapshot,
    TradeAction,
)
from trading_lab.execution.broker import (
    AlpacaPaperBrokerExecutor,
    VirtualLedgerBrokerExecutor,
    build_broker_executor,
)
from trading_lab.llm.ollama_engine import OllamaThesisEngine
from trading_lab.providers.market_data import (
    FallbackMarketDataProvider,
    SyntheticMarketDataProvider,
    YahooChartMarketDataProvider,
)
from trading_lab.providers.news import SyntheticNewsProvider
from trading_lab.risk.gate import DeterministicRiskGate
from trading_lab.scheduler.runner import TradingScheduler
from trading_lab.services.pipeline import TradingPipelineOrchestrator
from trading_lab.services.reflection import WeeklyReflectionService


def test_repository_bars_upsert_and_broker_factory(settings, repo) -> None:
    # Calling init_schema repeatedly remains idempotent and preserves seeded heuristics.
    repo.init_schema()
    assert repo.check_health()["status"] == "ok"
    assert repo.get_latest_heuristics().version == 1

    bars = make_bars("AAPL", [150.0 + i for i in range(60)])
    inserted = repo.upsert_bars(bars)
    assert inserted == 60
    # Re-upserting same timestamps remains idempotent (still 60 bars).
    repo.upsert_bars(bars)
    fetched = repo.get_bars("AAPL", limit=90)
    assert len(fetched) == 60
    assert fetched[-1].close == pytest.approx(209.0)

    default_broker = build_broker_executor(settings, repo)
    assert isinstance(default_broker, VirtualLedgerBrokerExecutor)
    assert default_broker.mode == "virtual_ledger"

    alpaca_settings = settings.model_copy(
        update={
            "alpaca_api_key": "PK_PAPER_KEY",
            "alpaca_secret_key": "SK_PAPER_SECRET",
            "alpaca_paper_base_url": "https://paper-api.alpaca.markets",
        }
    )
    alpaca_broker = build_broker_executor(alpaca_settings, repo)
    assert isinstance(alpaca_broker, AlpacaPaperBrokerExecutor)
    assert alpaca_broker.mode == "alpaca_paper"


@pytest.mark.asyncio
async def test_virtual_broker_buy_average_and_sell(settings, repo) -> None:
    broker = VirtualLedgerBrokerExecutor(repository=repo, initial_cash=settings.initial_cash)

    buy1 = await broker.execute_order(
        OrderRequest(
            thesis_id="t1",
            risk_decision_id="r1",
            symbol="AAPL",
            action=TradeAction.BUY,
            quantity=10.0,
            reference_price=200.0,
            stop_loss_price=194.0,
        )
    )
    assert buy1.status == "filled"
    assert await broker.get_account_cash() == pytest.approx(98000.0)

    buy2 = await broker.execute_order(
        OrderRequest(
            thesis_id="t2",
            risk_decision_id="r2",
            symbol="AAPL",
            action=TradeAction.BUY,
            quantity=10.0,
            reference_price=210.0,
            stop_loss_price=203.7,
        )
    )
    assert buy2.status == "filled"
    pos = repo.get_position("AAPL")
    assert pos is not None
    assert pos.quantity == pytest.approx(20.0)
    assert pos.avg_entry_price == pytest.approx(205.0)
    assert await broker.get_account_cash() == pytest.approx(95900.0)

    sell = await broker.execute_order(
        OrderRequest(
            thesis_id="t3",
            risk_decision_id="r3",
            symbol="AAPL",
            action=TradeAction.SELL,
            quantity=20.0,
            reference_price=220.0,
        )
    )
    assert sell.status == "filled"
    assert repo.get_position("AAPL") is None
    assert await broker.get_account_cash() == pytest.approx(100300.0)


@pytest.mark.asyncio
async def test_market_data_fallback_supplies_at_least_60_bars() -> None:
    def failing_yahoo(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    provider = FallbackMarketDataProvider(
        providers=[
            YahooChartMarketDataProvider(transport=httpx.MockTransport(failing_yahoo)),
            SyntheticMarketDataProvider(),
        ],
        min_bars=60,
    )
    bars = await provider.get_daily_bars("SPY", limit=80)
    assert len(bars) >= 60
    assert bars[0].source == "synthetic_fallback"


@pytest.mark.asyncio
async def test_weekly_reflection_clamps_weights_and_writes_artifact(settings, repo) -> None:
    t0 = datetime.now(UTC) - timedelta(days=5)
    t1 = datetime.now(UTC) - timedelta(days=1)
    repo.save_snapshot(
        PortfolioSnapshot(
            timestamp=t0,
            equity=100000.0,
            cash=100000.0,
            positions_value=0.0,
            daily_return_pct=0.0,
            daily_drawdown_pct=0.0,
            spy_price=500.0,
            spy_benchmark_equity=100000.0,
            alpha_vs_spy_pct=0.0,
        )
    )
    repo.save_snapshot(
        PortfolioSnapshot(
            timestamp=t1,
            equity=103000.0,
            cash=95000.0,
            positions_value=8000.0,
            daily_return_pct=0.01,
            daily_drawdown_pct=0.0,
            spy_price=505.0,
            spy_benchmark_equity=101000.0,
            alpha_vs_spy_pct=0.02,
        )
    )

    def extreme_weight_handler(_body: dict[str, Any]) -> httpx.Response:
        # Extreme candidate weights must be deterministically clamped to [0.05, 0.70] summing 1.0.
        content = json.dumps(
            {
                "summary": "Portfolio outperformed SPY by +2.0%.",
                "lessons_learned": ["Momentum filter added positive alpha."],
                "notes": "Extreme candidate weights test clamping.",
                "suggested_weights": {
                    "momentum_weight": 0.99,
                    "trend_weight": -0.50,
                    "mean_reversion_weight": 0.0,
                    "news_sentiment_weight": 5.0,
                    "volatility_penalty_weight": 0.001,
                },
            }
        )
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    llm = OllamaThesisEngine(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        transport=make_mock_ollama_transport(extreme_weight_handler),
    )
    svc = WeeklyReflectionService(settings=settings, repository=repo, llm_engine=llm)
    report = await svc.run_weekly_reflection(window_days=7)

    assert report.portfolio_return_pct == pytest.approx(0.03, abs=1e-4)
    assert report.spy_return_pct == pytest.approx(0.01, abs=1e-4)
    assert report.alpha_vs_spy_pct == pytest.approx(0.02, abs=1e-4)
    assert report.updated_weights.version == 2
    assert report.fallback_used is False

    weights = report.updated_weights.weight_map()
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-3)
    for w in weights.values():
        assert 0.05 <= w <= 0.70

    assert report.artifact_path is not None
    artifact = Path(report.artifact_path)
    assert artifact.exists()
    artifact_data = json.loads(artifact.read_text(encoding="utf-8"))
    assert artifact_data["id"] == report.id

    assert repo.get_latest_heuristics().version == 2
    assert len(repo.list_reflections()) == 1


def test_fastapi_dashboard_and_end_to_end_cycle_api(test_client) -> None:
    health_resp = test_client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"
    assert health_resp.json()["paper_only"] is True

    status_resp = test_client.get("/api/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["ollama"]["status"] == "ok"

    # Trigger full end-to-end cycle: AAPL BUY approved, NVDA BUY rejected (>5%), others HOLD.
    cycle_resp = test_client.post("/api/cycles/run")
    assert cycle_resp.status_code == 200
    cycle_data = cycle_resp.json()
    assert cycle_data["theses_generated"] == 4
    assert cycle_data["decisions_approved"] == 1
    assert cycle_data["decisions_rejected"] == 1
    assert cycle_data["orders_executed"] == 1

    pos_resp = test_client.get("/api/positions")
    assert pos_resp.status_code == 200
    assert pos_resp.json()["count"] == 1
    assert pos_resp.json()["positions"][0]["symbol"] == "AAPL"

    rej_resp = test_client.get("/api/risk-decisions?rejected_only=true")
    assert rej_resp.status_code == 200
    assert rej_resp.json()["count"] == 1
    assert rej_resp.json()["decisions"][0]["rule_code"] == "RULE_MAX_POSITION_CAP"

    # Trigger reflection via API.
    ref_resp = test_client.post("/api/reflections/run")
    assert ref_resp.status_code == 200
    assert ref_resp.json()["updated_weights"]["version"] == 2

    # Render HTML dashboard and verify marker + key sections.
    dash_resp = test_client.get("/")
    assert dash_resp.status_code == 200
    html = dash_resp.text
    assert "Trading Lab — Autonomous Paper-Trading Dashboard" in html
    assert 'data-trading-lab-health="ok"' in html
    assert "RULE_MAX_POSITION_CAP" in html
    assert "AAPL" in html


@pytest.mark.asyncio
async def test_scheduler_lifecycle_and_job_audit(settings, repo) -> None:
    sched_settings = settings.model_copy(update={"scheduler_enabled": True})

    def hold_handler(_body: dict[str, Any]) -> httpx.Response:
        content = json.dumps(
            {
                "action": "HOLD",
                "confidence": 0.50,
                "sentiment_score": 0.0,
                "target_position_pct": 0.0,
                "stop_loss_pct": 0.03,
                "catalyst_summary": "Neutral",
                "rationale": "Wait",
            }
        )
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    llm = OllamaThesisEngine(
        base_url=sched_settings.ollama_base_url,
        model=sched_settings.ollama_model,
        transport=make_mock_ollama_transport(hold_handler),
    )
    broker = VirtualLedgerBrokerExecutor(repository=repo, initial_cash=sched_settings.initial_cash)
    orchestrator = TradingPipelineOrchestrator(
        settings=sched_settings,
        market_data=SyntheticMarketDataProvider(),
        news_provider=SyntheticNewsProvider(),
        quant_analyzer=DeterministicQuantitativeAnalyzer(),
        llm_engine=llm,
        risk_gate=DeterministicRiskGate(sched_settings),
        broker=broker,
        repository=repo,
        reflection_service=WeeklyReflectionService(
            settings=sched_settings, repository=repo, llm_engine=llm
        ),
    )
    scheduler = TradingScheduler(
        settings=sched_settings,
        orchestrator=orchestrator,
        repository=repo,
    )

    scheduler.start()
    try:
        st = scheduler.status()
        assert st["running"] is True
        job_ids = {j["id"] for j in st["jobs"]}
        assert job_ids == {"market_trading_cycle", "weekend_reflection"}
        assert all(j["next_run_time"] is not None for j in st["jobs"])

        await scheduler.run_market_job()
        runs = repo.list_scheduler_runs()
        assert len(runs) == 1
        assert runs[0].job_name == "market_trading_cycle"
        assert runs[0].status == "success"
    finally:
        scheduler.shutdown()

    assert scheduler.status()["running"] is False
