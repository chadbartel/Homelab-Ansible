"""End-to-end autonomous paper-trading cycle orchestrator."""

from __future__ import annotations

import asyncio
import logging

from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import (
    CycleSummary,
    OrderRequest,
    PortfolioSnapshot,
    PositionRecord,
    ReflectionReport,
    utc_now,
)
from trading_lab.interfaces.contracts import (
    BrokerExecutor,
    LLMThesisEngine,
    MarketDataProvider,
    NewsProvider,
    QuantitativeAnalyzer,
    ReflectionService,
    RiskGate,
    TradeLedgerRepository,
)

logger = logging.getLogger(__name__)


class TradingPipelineOrchestrator:
    """Coordinates ingest -> quant -> LLM thesis -> RiskGate -> broker -> ledger -> snapshot."""

    def __init__(
        self,
        *,
        settings: TradingLabSettings,
        market_data: MarketDataProvider,
        news_provider: NewsProvider,
        quant_analyzer: QuantitativeAnalyzer,
        llm_engine: LLMThesisEngine,
        risk_gate: RiskGate,
        broker: BrokerExecutor,
        repository: TradeLedgerRepository,
        reflection_service: ReflectionService,
    ) -> None:
        self._settings = settings
        self._market_data = market_data
        self._news = news_provider
        self._quant = quant_analyzer
        self._llm = llm_engine
        self._risk_gate = risk_gate
        self._broker = broker
        self._repo = repository
        self._reflection = reflection_service
        self._lock = asyncio.Lock()

    async def run_trading_cycle(self) -> CycleSummary:
        async with self._lock:
            return await self._run_trading_cycle_locked()

    async def _run_trading_cycle_locked(self) -> CycleSummary:
        started_at = utc_now()
        allowlist = self._settings.allowlist_symbols
        benchmark = self._settings.benchmark_symbol.upper()
        ingest_symbols = list(dict.fromkeys([*allowlist, benchmark]))

        bars_by_symbol = {}
        latest_prices: dict[str, float] = {}

        for symbol in ingest_symbols:
            bars = await self._market_data.get_daily_bars(
                symbol, limit=self._settings.lookback_bars
            )
            self._repo.upsert_bars(bars)
            bars_by_symbol[symbol] = bars
            if bars:
                latest_prices[symbol] = float(bars[-1].close)

        spy_price = latest_prices.get(benchmark, 500.0)
        initial_spy = self._repo.get_initial_spy_price()
        if initial_spy is None or initial_spy <= 0:
            self._repo.set_initial_spy_price(spy_price)
            initial_spy = spy_price

        heuristics = self._repo.get_latest_heuristics()

        theses_generated = 0
        decisions_approved = 0
        decisions_rejected = 0
        orders_executed = 0

        for symbol in allowlist:
            bars = bars_by_symbol.get(symbol, [])
            if len(bars) < 50:
                logger.warning("Skipping %s: insufficient bars (%d)", symbol, len(bars))
                continue

            indicators = self._quant.compute_indicators(symbol, bars)
            news = await self._news.get_recent_news(symbol, limit=5)

            positions = await self._broker.get_positions(latest_prices)
            pos_map: dict[str, PositionRecord] = {p.symbol: p for p in positions}
            current_position = pos_map.get(symbol)
            cash = await self._broker.get_account_cash()

            current_snapshot = self._build_snapshot(
                cash=cash,
                positions=positions,
                spy_price=spy_price,
                initial_spy=initial_spy,
            )

            thesis = await self._llm.generate_thesis(
                indicators=indicators,
                news=news,
                heuristics=heuristics,
                current_position=current_position,
            )
            self._repo.save_thesis(thesis)
            theses_generated += 1

            decision = self._risk_gate.evaluate(
                thesis=thesis,
                indicators=indicators,
                snapshot=current_snapshot,
                current_position=current_position,
                broker_mode=self._broker.mode,
            )
            self._repo.save_risk_decision(decision)

            if decision.approved:
                decisions_approved += 1
                order_req = OrderRequest(
                    thesis_id=thesis.id,
                    risk_decision_id=decision.id,
                    symbol=symbol,
                    action=thesis.action,
                    quantity=decision.approved_quantity,
                    reference_price=indicators.latest_close,
                    stop_loss_price=decision.approved_stop_loss_price,
                    stop_loss_pct=thesis.stop_loss_pct,
                    paper_only=self._settings.paper_only,
                )
                execution = await self._broker.execute_order(order_req)
                self._repo.save_execution(execution)
                if execution.status in {"filled", "submitted", "accepted", "new"}:
                    orders_executed += 1
            elif decision.rule_code != "HOLD_NO_ACTION":
                decisions_rejected += 1

        final_positions = await self._broker.get_positions(latest_prices)
        final_cash = await self._broker.get_account_cash()
        final_snapshot = self._build_snapshot(
            cash=final_cash,
            positions=final_positions,
            spy_price=spy_price,
            initial_spy=initial_spy,
        )
        self._repo.save_snapshot(final_snapshot)

        return CycleSummary(
            started_at=started_at,
            finished_at=utc_now(),
            broker_mode=self._broker.mode,
            symbols_processed=allowlist,
            theses_generated=theses_generated,
            decisions_approved=decisions_approved,
            decisions_rejected=decisions_rejected,
            orders_executed=orders_executed,
            snapshot=final_snapshot,
        )

    async def run_weekly_reflection(self, window_days: int = 7) -> ReflectionReport:
        async with self._lock:
            return await self._reflection.run_weekly_reflection(window_days=window_days)

    def _build_snapshot(
        self,
        *,
        cash: float,
        positions: list[PositionRecord],
        spy_price: float,
        initial_spy: float,
    ) -> PortfolioSnapshot:
        now = utc_now()
        positions_value = round(sum(p.market_value for p in positions), 4)
        equity = round(cash + positions_value, 4)

        day_str = now.strftime("%Y-%m-%d")
        if hasattr(self._repo, "get_day_anchor"):
            day_anchor = self._repo.get_day_anchor(day_str, equity)
        else:
            day_anchor = self._settings.initial_cash

        daily_return_pct = (
            round((equity - day_anchor) / day_anchor, 6) if day_anchor > 0 else 0.0
        )
        daily_drawdown_pct = (
            round(max(0.0, (day_anchor - equity) / day_anchor), 6) if day_anchor > 0 else 0.0
        )

        spy_ratio = (spy_price / initial_spy) if initial_spy > 0 else 1.0
        spy_benchmark_equity = round(self._settings.initial_cash * spy_ratio, 4)
        port_total_ret = (equity / self._settings.initial_cash) - 1.0
        spy_total_ret = spy_ratio - 1.0
        alpha_vs_spy_pct = round(port_total_ret - spy_total_ret, 6)

        return PortfolioSnapshot(
            timestamp=now,
            equity=equity,
            cash=round(cash, 4),
            positions_value=positions_value,
            daily_return_pct=daily_return_pct,
            daily_drawdown_pct=daily_drawdown_pct,
            spy_price=round(spy_price, 4),
            spy_benchmark_equity=spy_benchmark_equity,
            alpha_vs_spy_pct=alpha_vs_spy_pct,
            broker_mode=self._broker.mode,
        )
