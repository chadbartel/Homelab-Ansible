"""SQLAlchemy 2.0 ledger repository supporting TimescaleDB (PG16) and SQLite."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    asc,
    create_engine,
    delete,
    desc,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from trading_lab.domain.models import (
    Bar,
    HeuristicWeights,
    OrderExecution,
    PortfolioSnapshot,
    PositionRecord,
    ReflectionReport,
    RiskDecision,
    SchedulerRunRecord,
    TradeAction,
    TradeThesis,
    new_id,
    utc_now,
)
from trading_lab.interfaces.contracts import TradeLedgerRepository

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class TimescaleTradeLedgerRepository(TradeLedgerRepository):
    """Persists all Trading Lab entities with TimescaleDB hypertables on PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine = self._create_engine(database_url)
        self.metadata = MetaData()
        self._define_tables()

    @staticmethod
    def _create_engine(database_url: str) -> Engine:
        if database_url.startswith("sqlite") and ":memory:" in database_url:
            return create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                future=True,
            )
        if database_url.startswith("sqlite"):
            return create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                future=True,
            )
        return create_engine(database_url, pool_pre_ping=True, future=True)

    def _define_tables(self) -> None:
        self.market_bars = Table(
            "market_bars",
            self.metadata,
            Column("symbol", String(16), primary_key=True),
            Column("timestamp", DateTime(timezone=True), primary_key=True),
            Column("open", Float, nullable=False),
            Column("high", Float, nullable=False),
            Column("low", Float, nullable=False),
            Column("close", Float, nullable=False),
            Column("volume", Float, nullable=False),
            Column("source", String(32), nullable=False),
        )

        self.trade_theses = Table(
            "trade_theses",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False, index=True),
            Column("symbol", String(16), nullable=False, index=True),
            Column("action", String(16), nullable=False),
            Column("confidence", Float, nullable=False),
            Column("sentiment_score", Float, nullable=False),
            Column("target_position_pct", Float, nullable=False),
            Column("stop_loss_pct", Float, nullable=True),
            Column("catalyst_summary", Text, nullable=False),
            Column("rationale", Text, nullable=False),
            Column("model_name", String(128), nullable=False),
            Column("heuristics_version", Integer, nullable=False),
            Column("fallback_used", Boolean, nullable=False),
            Column("raw_response", Text, nullable=True),
        )

        self.risk_decisions = Table(
            "risk_decisions",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False, index=True),
            Column("thesis_id", String(64), nullable=False, index=True),
            Column("symbol", String(16), nullable=False, index=True),
            Column("requested_action", String(16), nullable=False),
            Column("approved", Boolean, nullable=False),
            Column("rule_code", String(64), nullable=False),
            Column("reason", Text, nullable=False),
            Column("requested_notional", Float, nullable=False),
            Column("approved_quantity", Float, nullable=False),
            Column("approved_stop_loss_price", Float, nullable=True),
            Column("portfolio_equity", Float, nullable=False),
            Column("daily_drawdown_pct", Float, nullable=False),
        )

        self.order_executions = Table(
            "order_executions",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("executed_at", DateTime(timezone=True), nullable=False, index=True),
            Column("thesis_id", String(64), nullable=False),
            Column("risk_decision_id", String(64), nullable=False),
            Column("broker_mode", String(32), nullable=False),
            Column("broker_order_id", String(128), nullable=False),
            Column("symbol", String(16), nullable=False, index=True),
            Column("action", String(16), nullable=False),
            Column("quantity", Float, nullable=False),
            Column("fill_price", Float, nullable=False),
            Column("notional", Float, nullable=False),
            Column("stop_loss_price", Float, nullable=True),
            Column("status", String(32), nullable=False),
            Column("message", Text, nullable=False),
        )

        self.positions = Table(
            "positions",
            self.metadata,
            Column("symbol", String(16), primary_key=True),
            Column("quantity", Float, nullable=False),
            Column("avg_entry_price", Float, nullable=False),
            Column("market_price", Float, nullable=False),
            Column("stop_loss_price", Float, nullable=True),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )

        self.portfolio_snapshots = Table(
            "portfolio_snapshots",
            self.metadata,
            Column("timestamp", DateTime(timezone=True), primary_key=True),
            Column("id", String(64), primary_key=True),
            Column("equity", Float, nullable=False),
            Column("cash", Float, nullable=False),
            Column("positions_value", Float, nullable=False),
            Column("daily_return_pct", Float, nullable=False),
            Column("daily_drawdown_pct", Float, nullable=False),
            Column("spy_price", Float, nullable=False),
            Column("spy_benchmark_equity", Float, nullable=False),
            Column("alpha_vs_spy_pct", Float, nullable=False),
            Column("broker_mode", String(32), nullable=False),
        )

        self.heuristic_weights = Table(
            "heuristic_weights",
            self.metadata,
            Column("version", Integer, primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("momentum_weight", Float, nullable=False),
            Column("trend_weight", Float, nullable=False),
            Column("mean_reversion_weight", Float, nullable=False),
            Column("news_sentiment_weight", Float, nullable=False),
            Column("volatility_penalty_weight", Float, nullable=False),
            Column("notes", Text, nullable=False),
        )

        self.reflection_reports = Table(
            "reflection_reports",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False, index=True),
            Column("window_days", Integer, nullable=False),
            Column("portfolio_return_pct", Float, nullable=False),
            Column("spy_return_pct", Float, nullable=False),
            Column("alpha_vs_spy_pct", Float, nullable=False),
            Column("total_theses", Integer, nullable=False),
            Column("total_executions", Integer, nullable=False),
            Column("total_rejections", Integer, nullable=False),
            Column("summary", Text, nullable=False),
            Column("lessons_learned_json", Text, nullable=False),
            Column("previous_weights_json", Text, nullable=False),
            Column("updated_weights_json", Text, nullable=False),
            Column("artifact_path", Text, nullable=True),
            Column("model_name", String(128), nullable=False),
            Column("fallback_used", Boolean, nullable=False),
        )

        self.scheduler_runs = Table(
            "scheduler_runs",
            self.metadata,
            Column("id", String(64), primary_key=True),
            Column("job_name", String(64), nullable=False, index=True),
            Column("started_at", DateTime(timezone=True), nullable=False, index=True),
            Column("finished_at", DateTime(timezone=True), nullable=True),
            Column("status", String(32), nullable=False),
            Column("summary", Text, nullable=False),
        )

        self.portfolio_state = Table(
            "portfolio_state",
            self.metadata,
            Column("key", String(64), primary_key=True),
            Column("value", Text, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )

    def init_schema(self) -> None:
        self.metadata.create_all(self.engine)
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
                conn.execute(
                    text(
                        "SELECT create_hypertable('market_bars', 'timestamp', "
                        "if_not_exists => TRUE);"
                    )
                )
                conn.execute(
                    text(
                        "SELECT create_hypertable('portfolio_snapshots', 'timestamp', "
                        "if_not_exists => TRUE);"
                    )
                )
            logger.info("Initialized PostgreSQL/TimescaleDB hypertables.")
        self.get_latest_heuristics()

    def check_health(self) -> dict[str, object]:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok", "dialect": self.engine.dialect.name}
        except Exception as exc:
            return {"status": "error", "dialect": self.engine.dialect.name, "error": str(exc)}

    def upsert_bars(self, bars: list[Bar]) -> int:
        if not bars:
            return 0
        count = 0
        with self.engine.begin() as conn:
            for bar in bars:
                ts = _ensure_utc(bar.timestamp)
                assert ts is not None
                stmt_exists = select(self.market_bars.c.symbol).where(
                    and_(
                        self.market_bars.c.symbol == bar.symbol.upper(),
                        self.market_bars.c.timestamp == ts,
                    )
                )
                exists = conn.execute(stmt_exists).first()
                values = {
                    "symbol": bar.symbol.upper(),
                    "timestamp": ts,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "source": bar.source,
                }
                if exists:
                    conn.execute(
                        self.market_bars.update()
                        .where(
                            and_(
                                self.market_bars.c.symbol == bar.symbol.upper(),
                                self.market_bars.c.timestamp == ts,
                            )
                        )
                        .values(**values)
                    )
                else:
                    conn.execute(self.market_bars.insert().values(**values))
                count += 1
        return count

    def get_bars(self, symbol: str, limit: int = 90) -> list[Bar]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(self.market_bars)
                    .where(self.market_bars.c.symbol == symbol.upper())
                    .order_by(desc(self.market_bars.c.timestamp))
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        bars = [
            Bar(
                symbol=row["symbol"],
                timestamp=_ensure_utc(row["timestamp"]) or utc_now(),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                source=row["source"],
            )
            for row in rows
        ]
        bars.reverse()
        return bars

    def save_thesis(self, thesis: TradeThesis) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                self.trade_theses.insert().values(
                    id=thesis.id,
                    created_at=_ensure_utc(thesis.created_at),
                    symbol=thesis.symbol.upper(),
                    action=thesis.action.value,
                    confidence=thesis.confidence,
                    sentiment_score=thesis.sentiment_score,
                    target_position_pct=thesis.target_position_pct,
                    stop_loss_pct=thesis.stop_loss_pct,
                    catalyst_summary=thesis.catalyst_summary,
                    rationale=thesis.rationale,
                    model_name=thesis.model_name,
                    heuristics_version=thesis.heuristics_version,
                    fallback_used=thesis.fallback_used,
                    raw_response=thesis.raw_response,
                )
            )

    def list_theses(self, limit: int = 50) -> list[TradeThesis]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(self.trade_theses)
                    .order_by(desc(self.trade_theses.c.created_at))
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [
            TradeThesis(
                id=r["id"],
                created_at=_ensure_utc(r["created_at"]) or utc_now(),
                symbol=r["symbol"],
                action=TradeAction(r["action"]),
                confidence=r["confidence"],
                sentiment_score=r["sentiment_score"],
                target_position_pct=r["target_position_pct"],
                stop_loss_pct=r["stop_loss_pct"],
                catalyst_summary=r["catalyst_summary"],
                rationale=r["rationale"],
                model_name=r["model_name"],
                heuristics_version=r["heuristics_version"],
                fallback_used=bool(r["fallback_used"]),
                raw_response=r["raw_response"],
            )
            for r in rows
        ]

    def save_risk_decision(self, decision: RiskDecision) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                self.risk_decisions.insert().values(
                    id=decision.id,
                    created_at=_ensure_utc(decision.created_at),
                    thesis_id=decision.thesis_id,
                    symbol=decision.symbol.upper(),
                    requested_action=decision.requested_action.value,
                    approved=decision.approved,
                    rule_code=decision.rule_code,
                    reason=decision.reason,
                    requested_notional=decision.requested_notional,
                    approved_quantity=decision.approved_quantity,
                    approved_stop_loss_price=decision.approved_stop_loss_price,
                    portfolio_equity=decision.portfolio_equity,
                    daily_drawdown_pct=decision.daily_drawdown_pct,
                )
            )

    def list_risk_decisions(self, limit: int = 100) -> list[RiskDecision]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(self.risk_decisions)
                    .order_by(desc(self.risk_decisions.c.created_at))
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [
            RiskDecision(
                id=r["id"],
                created_at=_ensure_utc(r["created_at"]) or utc_now(),
                thesis_id=r["thesis_id"],
                symbol=r["symbol"],
                requested_action=TradeAction(r["requested_action"]),
                approved=bool(r["approved"]),
                rule_code=r["rule_code"],
                reason=r["reason"],
                requested_notional=r["requested_notional"],
                approved_quantity=r["approved_quantity"],
                approved_stop_loss_price=r["approved_stop_loss_price"],
                portfolio_equity=r["portfolio_equity"],
                daily_drawdown_pct=r["daily_drawdown_pct"],
            )
            for r in rows
        ]

    def save_execution(self, execution: OrderExecution) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                self.order_executions.insert().values(
                    id=execution.id,
                    executed_at=_ensure_utc(execution.executed_at),
                    thesis_id=execution.thesis_id,
                    risk_decision_id=execution.risk_decision_id,
                    broker_mode=execution.broker_mode,
                    broker_order_id=execution.broker_order_id,
                    symbol=execution.symbol.upper(),
                    action=execution.action.value,
                    quantity=execution.quantity,
                    fill_price=execution.fill_price,
                    notional=execution.notional,
                    stop_loss_price=execution.stop_loss_price,
                    status=execution.status,
                    message=execution.message,
                )
            )

    def list_executions(self, limit: int = 100) -> list[OrderExecution]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(self.order_executions)
                    .order_by(desc(self.order_executions.c.executed_at))
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [
            OrderExecution(
                id=r["id"],
                executed_at=_ensure_utc(r["executed_at"]) or utc_now(),
                thesis_id=r["thesis_id"],
                risk_decision_id=r["risk_decision_id"],
                broker_mode=r["broker_mode"],
                broker_order_id=r["broker_order_id"],
                symbol=r["symbol"],
                action=TradeAction(r["action"]),
                quantity=r["quantity"],
                fill_price=r["fill_price"],
                notional=r["notional"],
                stop_loss_price=r["stop_loss_price"],
                status=r["status"],
                message=r["message"],
            )
            for r in rows
        ]

    def _get_state(self, key: str) -> str | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(self.portfolio_state.c.value).where(self.portfolio_state.c.key == key)
            ).first()
        return str(row[0]) if row is not None else None

    def _set_state(self, key: str, value: str) -> None:
        now = utc_now()
        with self.engine.begin() as conn:
            exists = conn.execute(
                select(self.portfolio_state.c.key).where(self.portfolio_state.c.key == key)
            ).first()
            if exists:
                conn.execute(
                    self.portfolio_state.update()
                    .where(self.portfolio_state.c.key == key)
                    .values(value=value, updated_at=now)
                )
            else:
                conn.execute(
                    self.portfolio_state.insert().values(key=key, value=value, updated_at=now)
                )

    def get_cash(self, initial_cash: float) -> float:
        raw = self._get_state("cash")
        if raw is None:
            self._set_state("cash", f"{initial_cash:.4f}")
            return float(initial_cash)
        return float(raw)

    def set_cash(self, cash: float) -> None:
        self._set_state("cash", f"{cash:.4f}")

    def get_initial_spy_price(self) -> float | None:
        raw = self._get_state("initial_spy_price")
        return float(raw) if raw is not None else None

    def set_initial_spy_price(self, price: float) -> None:
        self._set_state("initial_spy_price", f"{price:.6f}")

    def get_day_anchor(self, day_str: str, fallback_equity: float) -> float:
        stored_day = self._get_state("day_anchor_date")
        stored_eq = self._get_state("day_anchor_equity")
        if stored_day != day_str or stored_eq is None:
            self._set_state("day_anchor_date", day_str)
            self._set_state("day_anchor_equity", f"{fallback_equity:.4f}")
            return fallback_equity
        return float(stored_eq)

    def get_position(self, symbol: str) -> PositionRecord | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(self.positions).where(self.positions.c.symbol == symbol.upper())
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return PositionRecord(
            symbol=row["symbol"],
            quantity=row["quantity"],
            avg_entry_price=row["avg_entry_price"],
            market_price=row["market_price"],
            stop_loss_price=row["stop_loss_price"],
            updated_at=_ensure_utc(row["updated_at"]) or utc_now(),
        )

    def list_positions(self) -> list[PositionRecord]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(select(self.positions).order_by(asc(self.positions.c.symbol)))
                .mappings()
                .all()
            )
        return [
            PositionRecord(
                symbol=r["symbol"],
                quantity=r["quantity"],
                avg_entry_price=r["avg_entry_price"],
                market_price=r["market_price"],
                stop_loss_price=r["stop_loss_price"],
                updated_at=_ensure_utc(r["updated_at"]) or utc_now(),
            )
            for r in rows
        ]

    def upsert_position(self, position: PositionRecord) -> None:
        sym = position.symbol.upper()
        values = {
            "symbol": sym,
            "quantity": position.quantity,
            "avg_entry_price": position.avg_entry_price,
            "market_price": position.market_price,
            "stop_loss_price": position.stop_loss_price,
            "updated_at": _ensure_utc(position.updated_at),
        }
        with self.engine.begin() as conn:
            exists = conn.execute(
                select(self.positions.c.symbol).where(self.positions.c.symbol == sym)
            ).first()
            if exists:
                conn.execute(
                    self.positions.update()
                    .where(self.positions.c.symbol == sym)
                    .values(**values)
                )
            else:
                conn.execute(self.positions.insert().values(**values))

    def delete_position(self, symbol: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(self.positions).where(self.positions.c.symbol == symbol.upper()))

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                self.portfolio_snapshots.insert().values(
                    timestamp=_ensure_utc(snapshot.timestamp),
                    id=new_id(),
                    equity=snapshot.equity,
                    cash=snapshot.cash,
                    positions_value=snapshot.positions_value,
                    daily_return_pct=snapshot.daily_return_pct,
                    daily_drawdown_pct=snapshot.daily_drawdown_pct,
                    spy_price=snapshot.spy_price,
                    spy_benchmark_equity=snapshot.spy_benchmark_equity,
                    alpha_vs_spy_pct=snapshot.alpha_vs_spy_pct,
                    broker_mode=snapshot.broker_mode,
                )
            )

    def list_snapshots(self, limit: int = 200) -> list[PortfolioSnapshot]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(self.portfolio_snapshots)
                    .order_by(desc(self.portfolio_snapshots.c.timestamp))
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        snapshots = [
            PortfolioSnapshot(
                timestamp=_ensure_utc(r["timestamp"]) or utc_now(),
                equity=r["equity"],
                cash=r["cash"],
                positions_value=r["positions_value"],
                daily_return_pct=r["daily_return_pct"],
                daily_drawdown_pct=r["daily_drawdown_pct"],
                spy_price=r["spy_price"],
                spy_benchmark_equity=r["spy_benchmark_equity"],
                alpha_vs_spy_pct=r["alpha_vs_spy_pct"],
                broker_mode=r["broker_mode"],
            )
            for r in rows
        ]
        snapshots.reverse()
        return snapshots

    def get_latest_snapshot(self) -> PortfolioSnapshot | None:
        snaps = self.list_snapshots(limit=1)
        return snaps[-1] if snaps else None

    def save_heuristics(self, weights: HeuristicWeights) -> None:
        with self.engine.begin() as conn:
            exists = conn.execute(
                select(self.heuristic_weights.c.version).where(
                    self.heuristic_weights.c.version == weights.version
                )
            ).first()
            values = {
                "version": weights.version,
                "created_at": _ensure_utc(weights.created_at),
                "momentum_weight": weights.momentum_weight,
                "trend_weight": weights.trend_weight,
                "mean_reversion_weight": weights.mean_reversion_weight,
                "news_sentiment_weight": weights.news_sentiment_weight,
                "volatility_penalty_weight": weights.volatility_penalty_weight,
                "notes": weights.notes,
            }
            if exists:
                conn.execute(
                    self.heuristic_weights.update()
                    .where(self.heuristic_weights.c.version == weights.version)
                    .values(**values)
                )
            else:
                conn.execute(self.heuristic_weights.insert().values(**values))

    def get_latest_heuristics(self) -> HeuristicWeights:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(self.heuristic_weights)
                    .order_by(desc(self.heuristic_weights.c.version))
                    .limit(1)
                )
                .mappings()
                .first()
            )
        if row is None:
            baseline = HeuristicWeights(version=1)
            self.save_heuristics(baseline)
            return baseline
        return HeuristicWeights(
            version=row["version"],
            created_at=_ensure_utc(row["created_at"]) or utc_now(),
            momentum_weight=row["momentum_weight"],
            trend_weight=row["trend_weight"],
            mean_reversion_weight=row["mean_reversion_weight"],
            news_sentiment_weight=row["news_sentiment_weight"],
            volatility_penalty_weight=row["volatility_penalty_weight"],
            notes=row["notes"],
        )

    def save_reflection(self, report: ReflectionReport) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                self.reflection_reports.insert().values(
                    id=report.id,
                    created_at=_ensure_utc(report.created_at),
                    window_days=report.window_days,
                    portfolio_return_pct=report.portfolio_return_pct,
                    spy_return_pct=report.spy_return_pct,
                    alpha_vs_spy_pct=report.alpha_vs_spy_pct,
                    total_theses=report.total_theses,
                    total_executions=report.total_executions,
                    total_rejections=report.total_rejections,
                    summary=report.summary,
                    lessons_learned_json=json.dumps(report.lessons_learned),
                    previous_weights_json=report.previous_weights.model_dump_json(),
                    updated_weights_json=report.updated_weights.model_dump_json(),
                    artifact_path=report.artifact_path,
                    model_name=report.model_name,
                    fallback_used=report.fallback_used,
                )
            )

    def list_reflections(self, limit: int = 20) -> list[ReflectionReport]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(self.reflection_reports)
                    .order_by(desc(self.reflection_reports.c.created_at))
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [
            ReflectionReport(
                id=r["id"],
                created_at=_ensure_utc(r["created_at"]) or utc_now(),
                window_days=r["window_days"],
                portfolio_return_pct=r["portfolio_return_pct"],
                spy_return_pct=r["spy_return_pct"],
                alpha_vs_spy_pct=r["alpha_vs_spy_pct"],
                total_theses=r["total_theses"],
                total_executions=r["total_executions"],
                total_rejections=r["total_rejections"],
                summary=r["summary"],
                lessons_learned=json.loads(r["lessons_learned_json"]),
                previous_weights=HeuristicWeights.model_validate_json(r["previous_weights_json"]),
                updated_weights=HeuristicWeights.model_validate_json(r["updated_weights_json"]),
                artifact_path=r["artifact_path"],
                model_name=r["model_name"],
                fallback_used=bool(r["fallback_used"]),
            )
            for r in rows
        ]

    def record_scheduler_run(self, run: SchedulerRunRecord) -> None:
        values = {
            "id": run.id,
            "job_name": run.job_name,
            "started_at": _ensure_utc(run.started_at),
            "finished_at": _ensure_utc(run.finished_at),
            "status": run.status,
            "summary": run.summary,
        }
        with self.engine.begin() as conn:
            exists = conn.execute(
                select(self.scheduler_runs.c.id).where(self.scheduler_runs.c.id == run.id)
            ).first()
            if exists:
                conn.execute(
                    self.scheduler_runs.update()
                    .where(self.scheduler_runs.c.id == run.id)
                    .values(**values)
                )
            else:
                conn.execute(self.scheduler_runs.insert().values(**values))

    def list_scheduler_runs(self, limit: int = 30) -> list[SchedulerRunRecord]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(self.scheduler_runs)
                    .order_by(desc(self.scheduler_runs.c.started_at))
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [
            SchedulerRunRecord(
                id=r["id"],
                job_name=r["job_name"],
                started_at=_ensure_utc(r["started_at"]) or utc_now(),
                finished_at=_ensure_utc(r["finished_at"]),
                status=r["status"],
                summary=r["summary"],
            )
            for r in rows
        ]
