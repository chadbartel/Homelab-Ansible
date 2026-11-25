"""FastAPI application factory, JSON API endpoints, and Jinja2 dark-mode dashboard."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from trading_lab.analytics.quantitative import DeterministicQuantitativeAnalyzer
from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import PortfolioSnapshot, SchedulerRunRecord, utc_now
from trading_lab.execution.broker import build_broker_executor
from trading_lab.interfaces.contracts import LLMThesisEngine, TradeLedgerRepository
from trading_lab.llm.ollama_engine import OllamaThesisEngine
from trading_lab.persistence.repository import TimescaleTradeLedgerRepository
from trading_lab.providers.market_data import build_market_data_provider
from trading_lab.providers.news import build_news_provider
from trading_lab.risk.gate import DeterministicRiskGate
from trading_lab.scheduler.runner import TradingScheduler
from trading_lab.services.pipeline import TradingPipelineOrchestrator
from trading_lab.services.reflection import WeeklyReflectionService

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _configure_logging(log_dir: str) -> None:
    root = logging.getLogger("trading_lab")
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    try:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path / "trading_lab.log", encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        # In read-only test containers or local test runs, stdout logging suffices.
        pass


def _build_svg_chart(
    snapshots: list[PortfolioSnapshot], initial_cash: float
) -> dict[str, Any]:
    """Compute inline SVG coordinates comparing portfolio equity vs SPY benchmark."""
    width = 760
    height = 240
    pad_left = 68
    pad_right = 20
    pad_top = 18
    pad_bottom = 32
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    if not snapshots:
        points = [(initial_cash, initial_cash, "Start"), (initial_cash, initial_cash, "Now")]
    elif len(snapshots) == 1:
        s = snapshots[0]
        label = s.timestamp.strftime("%m-%d %H:%M")
        points = [(initial_cash, initial_cash, "Init"), (s.equity, s.spy_benchmark_equity, label)]
    else:
        points = [
            (s.equity, s.spy_benchmark_equity, s.timestamp.strftime("%m-%d %H:%M"))
            for s in snapshots[-60:]
        ]

    all_vals = [v for p in points for v in (p[0], p[1])]
    min_val = min(all_vals)
    max_val = max(all_vals)
    span = max_val - min_val
    if span < 1.0:
        min_val -= max(initial_cash * 0.005, 50.0)
        max_val += max(initial_cash * 0.005, 50.0)
    else:
        margin = span * 0.12
        min_val -= margin
        max_val += margin

    denom = max(max_val - min_val, 1.0)
    n = len(points)

    def to_xy(idx: int, val: float) -> tuple[float, float]:
        x = pad_left + (plot_w * idx / max(n - 1, 1))
        y = pad_top + plot_h - ((val - min_val) / denom) * plot_h
        return round(x, 2), round(y, 2)

    port_coords = [to_xy(i, p[0]) for i, p in enumerate(points)]
    spy_coords = [to_xy(i, p[1]) for i, p in enumerate(points)]

    grid_lines = []
    for step in range(4):
        frac = step / 3.0
        val = max_val - frac * (max_val - min_val)
        y = round(pad_top + frac * plot_h, 2)
        grid_lines.append({"y": y, "label": f"${val:,.0f}"})

    return {
        "width": width,
        "height": height,
        "pad_left": pad_left,
        "pad_right": pad_right,
        "pad_bottom": pad_bottom,
        "portfolio_points": " ".join(f"{x},{y}" for x, y in port_coords),
        "spy_points": " ".join(f"{x},{y}" for x, y in spy_coords),
        "grid_lines": grid_lines,
        "start_label": points[0][2],
        "end_label": points[-1][2],
        "latest_portfolio": points[-1][0],
        "latest_spy": points[-1][1],
    }


def create_app(
    settings: TradingLabSettings | None = None,
    repository: TradeLedgerRepository | None = None,
    orchestrator: TradingPipelineOrchestrator | None = None,
    llm_engine: LLMThesisEngine | None = None,
    scheduler: TradingScheduler | None = None,
) -> FastAPI:
    """Create and wire the FastAPI Trading Lab application."""
    cfg = settings or TradingLabSettings()
    _configure_logging(cfg.log_dir)

    repo: TradeLedgerRepository = repository or TimescaleTradeLedgerRepository(cfg.database_url)
    llm: LLMThesisEngine = llm_engine or OllamaThesisEngine(
        base_url=cfg.ollama_base_url,
        model=cfg.ollama_model,
        timeout_seconds=cfg.ollama_timeout_seconds,
        default_stop_loss_pct=cfg.default_stop_loss_pct,
    )

    if orchestrator is None:
        market_data = build_market_data_provider(cfg)
        news_provider = build_news_provider(cfg)
        quant = DeterministicQuantitativeAnalyzer()
        risk_gate = DeterministicRiskGate(cfg)
        broker = build_broker_executor(cfg, repo)
        reflection_svc = WeeklyReflectionService(
            settings=cfg,
            repository=repo,
            llm_engine=llm,
        )
        pipe = TradingPipelineOrchestrator(
            settings=cfg,
            market_data=market_data,
            news_provider=news_provider,
            quant_analyzer=quant,
            llm_engine=llm,
            risk_gate=risk_gate,
            broker=broker,
            repository=repo,
            reflection_service=reflection_svc,
        )
    else:
        pipe = orchestrator

    sched = scheduler or TradingScheduler(
        settings=cfg,
        orchestrator=pipe,
        repository=repo,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repo.init_schema()
        sched.start()
        try:
            yield
        finally:
            sched.shutdown()

    app = FastAPI(
        title="Trading Lab — Autonomous Paper-Trading Lab",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = cfg
    app.state.repository = repo
    app.state.orchestrator = pipe
    app.state.llm_engine = llm
    app.state.scheduler = sched

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/health")
    async def health() -> dict[str, Any]:
        db_health = repo.check_health()
        sched_status = sched.status()
        overall = "ok" if db_health.get("status") == "ok" else "degraded"
        return {
            "status": overall,
            "service": "trading-lab",
            "paper_only": cfg.paper_only,
            "broker_mode": cfg.execution_mode,
            "database": db_health,
            "scheduler_running": sched_status["running"],
        }

    @app.get("/api/status")
    async def api_status() -> dict[str, Any]:
        ollama_health = await llm.check_health()
        db_health = repo.check_health()
        latest_snapshot = repo.get_latest_snapshot()
        heuristics = repo.get_latest_heuristics()
        return {
            "status": "ok" if db_health.get("status") == "ok" else "degraded",
            "broker_mode": cfg.execution_mode,
            "paper_only": cfg.paper_only,
            "allowlist": cfg.allowlist_symbols,
            "benchmark_symbol": cfg.benchmark_symbol,
            "database": db_health,
            "ollama": ollama_health,
            "scheduler": sched.status(),
            "heuristics": heuristics.model_dump(mode="json"),
            "latest_snapshot": (
                latest_snapshot.model_dump(mode="json") if latest_snapshot else None
            ),
        }

    @app.get("/api/portfolio")
    async def api_portfolio(limit: int = Query(default=120, ge=1, le=500)) -> dict[str, Any]:
        snapshots = repo.list_snapshots(limit=limit)
        latest = snapshots[-1] if snapshots else None
        cash = repo.get_cash(cfg.initial_cash)
        return {
            "broker_mode": cfg.execution_mode,
            "initial_cash": cfg.initial_cash,
            "cash": latest.cash if latest else cash,
            "latest_snapshot": latest.model_dump(mode="json") if latest else None,
            "snapshots": [s.model_dump(mode="json") for s in snapshots],
        }

    @app.get("/api/positions")
    async def api_positions() -> dict[str, Any]:
        positions = repo.list_positions()
        return {
            "count": len(positions),
            "positions": [
                {
                    **p.model_dump(mode="json"),
                    "market_value": p.market_value,
                    "cost_basis": p.cost_basis,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": p.unrealized_pnl_pct,
                }
                for p in positions
            ],
        }

    @app.get("/api/theses")
    async def api_theses(limit: int = Query(default=30, ge=1, le=200)) -> dict[str, Any]:
        theses = repo.list_theses(limit=limit)
        return {
            "count": len(theses),
            "theses": [t.model_dump(mode="json") for t in theses],
        }

    @app.get("/api/risk-decisions")
    async def api_risk_decisions(
        limit: int = Query(default=50, ge=1, le=200),
        rejected_only: bool = False,
    ) -> dict[str, Any]:
        decisions = repo.list_risk_decisions(limit=limit)
        if rejected_only:
            decisions = [
                d for d in decisions if not d.approved and d.rule_code != "HOLD_NO_ACTION"
            ]
        return {
            "count": len(decisions),
            "decisions": [d.model_dump(mode="json") for d in decisions],
        }

    @app.get("/api/reflections")
    async def api_reflections(limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
        reflections = repo.list_reflections(limit=limit)
        return {
            "count": len(reflections),
            "reflections": [r.model_dump(mode="json") for r in reflections],
        }

    @app.post("/api/cycles/run")
    async def api_run_cycle() -> dict[str, Any]:
        run = SchedulerRunRecord(job_name="manual_trading_cycle", status="running")
        repo.record_scheduler_run(run)
        try:
            summary = await pipe.run_trading_cycle()
            run.finished_at = utc_now()
            run.status = "success"
            run.summary = (
                f"Manual cycle: {len(summary.symbols_processed)} symbols, "
                f"{summary.orders_executed} executed, {summary.decisions_rejected} rejected"
            )
            repo.record_scheduler_run(run)
            return summary.model_dump(mode="json")
        except Exception as exc:
            run.finished_at = utc_now()
            run.status = "error"
            run.summary = f"{type(exc).__name__}: {exc}"
            repo.record_scheduler_run(run)
            raise

    @app.post("/api/reflections/run")
    async def api_run_reflection(
        window_days: int = Query(default=7, ge=1, le=90),
    ) -> dict[str, Any]:
        run = SchedulerRunRecord(job_name="manual_reflection", status="running")
        repo.record_scheduler_run(run)
        try:
            report = await pipe.run_weekly_reflection(window_days=window_days)
            run.finished_at = utc_now()
            run.status = "success"
            run.summary = (
                f"Manual reflection v{report.updated_weights.version}: "
                f"alpha={report.alpha_vs_spy_pct * 100:+.2f}%"
            )
            repo.record_scheduler_run(run)
            return report.model_dump(mode="json")
        except Exception as exc:
            run.finished_at = utc_now()
            run.status = "error"
            run.summary = f"{type(exc).__name__}: {exc}"
            repo.record_scheduler_run(run)
            raise

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        snapshots = repo.list_snapshots(limit=120)
        latest = snapshots[-1] if snapshots else None
        cash = latest.cash if latest else repo.get_cash(cfg.initial_cash)
        equity = latest.equity if latest else cash
        total_return_pct = (equity / cfg.initial_cash) - 1.0
        spy_equity = latest.spy_benchmark_equity if latest else cfg.initial_cash
        spy_return_pct = (spy_equity / cfg.initial_cash) - 1.0
        alpha_pct = latest.alpha_vs_spy_pct if latest else 0.0
        drawdown_pct = latest.daily_drawdown_pct if latest else 0.0

        positions = repo.list_positions()
        theses = repo.list_theses(limit=20)
        decisions = repo.list_risk_decisions(limit=25)
        reflections = repo.list_reflections(limit=5)
        heuristics = repo.get_latest_heuristics()
        scheduler_runs = repo.list_scheduler_runs(limit=12)
        sched_status = sched.status()
        ollama_health = await llm.check_health()
        chart = _build_svg_chart(snapshots, cfg.initial_cash)

        next_run = None
        for job in sched_status.get("jobs", []):
            if job.get("next_run_time"):
                next_run = job["next_run_time"]
                break

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "settings": cfg,
                "mode_label": (
                    "Alpaca Paper API"
                    if cfg.execution_mode == "alpaca_paper"
                    else "Virtual Ledger (Paper)"
                ),
                "equity": equity,
                "cash": cash,
                "total_return_pct": total_return_pct,
                "spy_return_pct": spy_return_pct,
                "alpha_pct": alpha_pct,
                "drawdown_pct": drawdown_pct,
                "latest_snapshot": latest,
                "chart": chart,
                "positions": positions,
                "theses": theses,
                "decisions": decisions,
                "reflections": reflections,
                "latest_reflection": reflections[0] if reflections else None,
                "heuristics": heuristics,
                "scheduler_status": sched_status,
                "scheduler_runs": scheduler_runs,
                "next_run": next_run,
                "ollama_health": ollama_health,
            },
        )

    return app
