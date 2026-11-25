"""Core typed domain entities for the Autonomous Paper-Trading Lab."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def new_id() -> str:
    """Generate a compact hex UUID."""
    return uuid4().hex


class TradeAction(StrEnum):
    """Supported directional actions."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Bar(BaseModel):
    """Single OHLCV market bar."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str = "unknown"


class NewsArticle(BaseModel):
    """Normalized market news article or headline."""

    symbol: str
    title: str
    summary: str = ""
    source: str = "unknown"
    url: str = ""
    published_at: datetime = Field(default_factory=utc_now)


class TechnicalIndicators(BaseModel):
    """Purely deterministic quantitative indicators computed from OHLCV bars."""

    symbol: str
    as_of: datetime
    latest_close: float
    rsi_14: float
    atr_14: float
    sma_20: float
    sma_50: float
    ema_12: float
    ema_26: float
    volatility_20d: float
    daily_return_pct: float
    momentum_20d_pct: float
    trend_regime: Literal["bullish", "bearish", "neutral"]
    quant_score: float = Field(ge=-1.0, le=1.0)
    bars_count: int


class HeuristicWeights(BaseModel):
    """Tunable prompt/strategy weights evolved during weekend reflections."""

    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    momentum_weight: float = Field(default=0.30, ge=0.05, le=0.70)
    trend_weight: float = Field(default=0.25, ge=0.05, le=0.70)
    mean_reversion_weight: float = Field(default=0.20, ge=0.05, le=0.70)
    news_sentiment_weight: float = Field(default=0.15, ge=0.05, le=0.70)
    volatility_penalty_weight: float = Field(default=0.10, ge=0.05, le=0.70)
    notes: str = "Initial baseline heuristics"

    def weight_map(self) -> dict[str, float]:
        """Return mapping of heuristic weight names to numeric values."""
        return {
            "momentum_weight": self.momentum_weight,
            "trend_weight": self.trend_weight,
            "mean_reversion_weight": self.mean_reversion_weight,
            "news_sentiment_weight": self.news_sentiment_weight,
            "volatility_penalty_weight": self.volatility_penalty_weight,
        }

    @classmethod
    def clamp_and_normalize(
        cls,
        raw_weights: dict[str, float],
        *,
        version: int,
        notes: str,
        min_weight: float = 0.05,
        max_weight: float = 0.70,
    ) -> HeuristicWeights:
        """Deterministically clamp candidate weights to [0.05, 0.70] and normalize to sum 1.0."""
        keys = (
            "momentum_weight",
            "trend_weight",
            "mean_reversion_weight",
            "news_sentiment_weight",
            "volatility_penalty_weight",
        )
        defaults = {
            "momentum_weight": 0.30,
            "trend_weight": 0.25,
            "mean_reversion_weight": 0.20,
            "news_sentiment_weight": 0.15,
            "volatility_penalty_weight": 0.10,
        }
        clamped: dict[str, float] = {}
        for key in keys:
            val = raw_weights.get(key, defaults[key])
            try:
                num = float(val)
            except (TypeError, ValueError):
                num = defaults[key]
            clamped[key] = max(min_weight, min(max_weight, num))

        # Iterative projection onto the simplex intersected with [min_weight, max_weight]^n.
        for _ in range(10):
            total = sum(clamped.values())
            if total <= 0:
                clamped = dict(defaults)
                break
            clamped = {k: v / total for k, v in clamped.items()}
            clamped = {k: max(min_weight, min(max_weight, v)) for k, v in clamped.items()}

        # Final exact normalization to sum 1.0 while respecting bounds.
        total = sum(clamped.values())
        normalized = {k: round(v / total, 4) for k, v in clamped.items()}
        diff = round(1.0 - sum(normalized.values()), 4)
        # Apply tiny rounding residual to the largest weight safely within bounds.
        largest_key = max(normalized, key=lambda k: normalized[k])
        normalized[largest_key] = round(
            max(min_weight, min(max_weight, normalized[largest_key] + diff)), 4
        )

        return cls(
            version=version,
            created_at=utc_now(),
            notes=notes,
            **normalized,
        )


class TradeThesis(BaseModel):
    """Structured trade proposal produced by the LLM thesis engine."""

    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    symbol: str
    action: TradeAction
    confidence: float = Field(ge=0.0, le=1.0)
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    target_position_pct: float = Field(default=0.03, ge=0.0, le=1.0)
    stop_loss_pct: float | None = Field(default=None)
    catalyst_summary: str
    rationale: str
    model_name: str
    heuristics_version: int = 1
    fallback_used: bool = False
    raw_response: str | None = None


class RiskDecision(BaseModel):
    """Deterministic audit verdict emitted by RiskGate."""

    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    thesis_id: str
    symbol: str
    requested_action: TradeAction
    approved: bool
    rule_code: str
    reason: str
    requested_notional: float = 0.0
    approved_quantity: float = 0.0
    approved_stop_loss_price: float | None = None
    portfolio_equity: float = 0.0
    daily_drawdown_pct: float = 0.0


class OrderRequest(BaseModel):
    """Approved paper order forwarded to BrokerExecutor."""

    thesis_id: str
    risk_decision_id: str
    symbol: str
    action: TradeAction
    quantity: float = Field(gt=0.0)
    reference_price: float = Field(gt=0.0)
    stop_loss_price: float | None = None
    stop_loss_pct: float | None = None
    paper_only: bool = True


class OrderExecution(BaseModel):
    """Executed paper order record."""

    id: str = Field(default_factory=new_id)
    executed_at: datetime = Field(default_factory=utc_now)
    thesis_id: str
    risk_decision_id: str
    broker_mode: str
    broker_order_id: str
    symbol: str
    action: TradeAction
    quantity: float
    fill_price: float
    notional: float
    stop_loss_price: float | None = None
    status: str
    message: str = ""


class PositionRecord(BaseModel):
    """Open portfolio position."""

    symbol: str
    quantity: float
    avg_entry_price: float
    market_price: float
    stop_loss_price: float | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def market_value(self) -> float:
        return round(self.quantity * self.market_price, 4)

    @property
    def cost_basis(self) -> float:
        return round(self.quantity * self.avg_entry_price, 4)

    @property
    def unrealized_pnl(self) -> float:
        return round(self.market_value - self.cost_basis, 4)

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis <= 0:
            return 0.0
        return round(self.unrealized_pnl / self.cost_basis, 6)


class PortfolioSnapshot(BaseModel):
    """Point-in-time portfolio valuation and SPY benchmark comparison."""

    timestamp: datetime = Field(default_factory=utc_now)
    equity: float
    cash: float
    positions_value: float
    daily_return_pct: float
    daily_drawdown_pct: float
    spy_price: float
    spy_benchmark_equity: float
    alpha_vs_spy_pct: float
    broker_mode: str = "virtual_ledger"


class ReflectionReport(BaseModel):
    """Weekend post-mortem report and updated heuristic weights."""

    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    window_days: int = 7
    portfolio_return_pct: float
    spy_return_pct: float
    alpha_vs_spy_pct: float
    total_theses: int
    total_executions: int
    total_rejections: int
    summary: str
    lessons_learned: list[str]
    previous_weights: HeuristicWeights
    updated_weights: HeuristicWeights
    artifact_path: str | None = None
    model_name: str
    fallback_used: bool = False


class SchedulerRunRecord(BaseModel):
    """Audit log entry for a scheduled or manually triggered job run."""

    id: str = Field(default_factory=new_id)
    job_name: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    status: str = "running"
    summary: str = ""


class CycleSummary(BaseModel):
    """Summary returned after a complete trading cycle run."""

    started_at: datetime
    finished_at: datetime
    broker_mode: str
    symbols_processed: list[str]
    theses_generated: int
    decisions_approved: int
    decisions_rejected: int
    orders_executed: int
    snapshot: PortfolioSnapshot
