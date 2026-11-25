"""SOLID interface contracts for Trading Lab subsystems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from trading_lab.domain.models import (
    Bar,
    HeuristicWeights,
    NewsArticle,
    OrderExecution,
    OrderRequest,
    PortfolioSnapshot,
    PositionRecord,
    ReflectionReport,
    RiskDecision,
    SchedulerRunRecord,
    TechnicalIndicators,
    TradeThesis,
)


class MarketDataProvider(ABC):
    """Retrieves historical OHLCV market bars."""

    @abstractmethod
    async def get_daily_bars(self, symbol: str, limit: int = 90) -> list[Bar]:
        """Return ascending daily OHLCV bars for symbol."""


class NewsProvider(ABC):
    """Retrieves recent market news headlines for catalyst analysis."""

    @abstractmethod
    async def get_recent_news(self, symbol: str, limit: int = 5) -> list[NewsArticle]:
        """Return recent news articles relevant to symbol."""


class QuantitativeAnalyzer(ABC):
    """Computes strictly deterministic technical indicators (zero LLM calls)."""

    @abstractmethod
    def compute_indicators(self, symbol: str, bars: list[Bar]) -> TechnicalIndicators:
        """Compute deterministic technical indicators from ascending daily bars."""


class LLMThesisEngine(ABC):
    """Synthesizes structured trade theses and weekend post-mortems via an LLM."""

    @abstractmethod
    async def generate_thesis(
        self,
        indicators: TechnicalIndicators,
        news: list[NewsArticle],
        heuristics: HeuristicWeights,
        current_position: PositionRecord | None = None,
    ) -> TradeThesis:
        """Produce a structured TradeThesis, falling back safely to HOLD on error."""

    @abstractmethod
    async def generate_reflection(
        self, context: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        """Produce structured weekend reflection JSON and a fallback_used flag."""

    @abstractmethod
    async def check_health(self) -> dict[str, Any]:
        """Return LLM backend health metadata."""


class RiskGate(ABC):
    """Enforces hard-coded deterministic financial safety guardrails."""

    @abstractmethod
    def evaluate(
        self,
        thesis: TradeThesis,
        indicators: TechnicalIndicators,
        snapshot: PortfolioSnapshot,
        current_position: PositionRecord | None,
        broker_mode: str,
    ) -> RiskDecision:
        """Evaluate a TradeThesis against all deterministic guardrails."""


class BrokerExecutor(ABC):
    """Executes approved paper-only orders."""

    @property
    @abstractmethod
    def mode(self) -> str:
        """Execution backend identifier ('alpaca_paper' or 'virtual_ledger')."""

    @abstractmethod
    async def execute_order(self, order: OrderRequest) -> OrderExecution:
        """Execute a paper-only order and return the execution audit record."""

    @abstractmethod
    async def get_account_cash(self) -> float:
        """Return available paper cash balance."""

    @abstractmethod
    async def get_positions(self, latest_prices: dict[str, float]) -> list[PositionRecord]:
        """Return current open positions marked to latest prices."""


class TradeLedgerRepository(ABC):
    """Persists market bars, theses, risk decisions, executions, positions, and snapshots."""

    @abstractmethod
    def init_schema(self) -> None:
        """Create tables and TimescaleDB hypertables idempotently."""

    @abstractmethod
    def check_health(self) -> dict[str, Any]:
        """Return database connectivity health metadata."""

    @abstractmethod
    def get_day_anchor(self, day_str: str, fallback_equity: float) -> float:
        """Return opening equity anchor for the given YYYY-MM-DD trading day."""

    @abstractmethod
    def upsert_bars(self, bars: list[Bar]) -> int:
        """Persist OHLCV bars idempotently."""

    @abstractmethod
    def get_bars(self, symbol: str, limit: int = 90) -> list[Bar]:
        """Return ascending historical bars for symbol."""

    @abstractmethod
    def save_thesis(self, thesis: TradeThesis) -> None:
        """Persist a TradeThesis."""

    @abstractmethod
    def list_theses(self, limit: int = 50) -> list[TradeThesis]:
        """Return most recent TradeTheses descending by created_at."""

    @abstractmethod
    def save_risk_decision(self, decision: RiskDecision) -> None:
        """Persist a RiskDecision."""

    @abstractmethod
    def list_risk_decisions(self, limit: int = 100) -> list[RiskDecision]:
        """Return most recent RiskDecisions descending by created_at."""

    @abstractmethod
    def save_execution(self, execution: OrderExecution) -> None:
        """Persist an OrderExecution."""

    @abstractmethod
    def list_executions(self, limit: int = 100) -> list[OrderExecution]:
        """Return most recent OrderExecutions descending by executed_at."""

    @abstractmethod
    def get_cash(self, initial_cash: float) -> float:
        """Return virtual ledger cash, initializing to initial_cash if absent."""

    @abstractmethod
    def set_cash(self, cash: float) -> None:
        """Update virtual ledger cash balance."""

    @abstractmethod
    def get_initial_spy_price(self) -> float | None:
        """Return initial SPY benchmark anchor price if stored."""

    @abstractmethod
    def set_initial_spy_price(self, price: float) -> None:
        """Store initial SPY benchmark anchor price."""

    @abstractmethod
    def get_position(self, symbol: str) -> PositionRecord | None:
        """Return open position for symbol if any."""

    @abstractmethod
    def list_positions(self) -> list[PositionRecord]:
        """Return all open positions."""

    @abstractmethod
    def upsert_position(self, position: PositionRecord) -> None:
        """Create or update an open position."""

    @abstractmethod
    def delete_position(self, symbol: str) -> None:
        """Remove a closed position."""

    @abstractmethod
    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Persist a point-in-time PortfolioSnapshot."""

    @abstractmethod
    def list_snapshots(self, limit: int = 200) -> list[PortfolioSnapshot]:
        """Return PortfolioSnapshots ascending by timestamp for charting."""

    @abstractmethod
    def get_latest_snapshot(self) -> PortfolioSnapshot | None:
        """Return the most recent PortfolioSnapshot if any."""

    @abstractmethod
    def save_heuristics(self, weights: HeuristicWeights) -> None:
        """Persist a versioned HeuristicWeights record."""

    @abstractmethod
    def get_latest_heuristics(self) -> HeuristicWeights:
        """Return the latest HeuristicWeights, seeding v1 if empty."""

    @abstractmethod
    def save_reflection(self, report: ReflectionReport) -> None:
        """Persist a weekend ReflectionReport."""

    @abstractmethod
    def list_reflections(self, limit: int = 20) -> list[ReflectionReport]:
        """Return most recent ReflectionReports descending by created_at."""

    @abstractmethod
    def record_scheduler_run(self, run: SchedulerRunRecord) -> None:
        """Insert or update a SchedulerRunRecord."""

    @abstractmethod
    def list_scheduler_runs(self, limit: int = 30) -> list[SchedulerRunRecord]:
        """Return most recent SchedulerRunRecords descending by started_at."""


class ReflectionService(ABC):
    """Runs weekly performance post-mortem vs SPY and evolves heuristic weights."""

    @abstractmethod
    async def run_weekly_reflection(self, window_days: int = 7) -> ReflectionReport:
        """Evaluate trailing performance vs SPY and save updated clamped heuristics."""
