"""AsyncIOScheduler integration for Trading Lab autonomous cadence."""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import SchedulerRunRecord, utc_now
from trading_lab.interfaces.contracts import TradeLedgerRepository
from trading_lab.services.pipeline import TradingPipelineOrchestrator

logger = logging.getLogger(__name__)


class TradingScheduler:
    """Manages weekday market-hours trading cycles and weekend reflection jobs."""

    MARKET_JOB_ID = "market_trading_cycle"
    REFLECTION_JOB_ID = "weekend_reflection"

    def __init__(
        self,
        *,
        settings: TradingLabSettings,
        orchestrator: TradingPipelineOrchestrator,
        repository: TradeLedgerRepository,
    ) -> None:
        self._settings = settings
        self._orchestrator = orchestrator
        self._repo = repository
        self._scheduler: AsyncIOScheduler | None = None

    def start(self) -> None:
        if not self._settings.scheduler_enabled:
            logger.info("TradingScheduler disabled via SCHEDULER_ENABLED=False")
            return
        if self._scheduler and self._scheduler.running:
            return

        scheduler = AsyncIOScheduler(timezone=self._settings.scheduler_timezone)
        scheduler.add_job(
            self.run_market_job,
            trigger=CronTrigger.from_crontab(
                self._settings.scheduler_market_cron,
                timezone=self._settings.scheduler_timezone,
            ),
            id=self.MARKET_JOB_ID,
            name="Weekday Market-Hours Trading Cycle",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            self.run_reflection_job,
            trigger=CronTrigger.from_crontab(
                self._settings.scheduler_reflection_cron,
                timezone=self._settings.scheduler_timezone,
            ),
            id=self.REFLECTION_JOB_ID,
            name="Weekend Strategy Reflection & Weight Tuning",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        self._scheduler = scheduler
        logger.info(
            "TradingScheduler started (market=%r, reflection=%r, tz=%s)",
            self._settings.scheduler_market_cron,
            self._settings.scheduler_reflection_cron,
            self._settings.scheduler_timezone,
        )

    def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("TradingScheduler shut down cleanly.")
        self._scheduler = None

    async def run_market_job(self) -> None:
        run = SchedulerRunRecord(job_name=self.MARKET_JOB_ID, status="running")
        self._repo.record_scheduler_run(run)
        try:
            summary = await self._orchestrator.run_trading_cycle()
            run.finished_at = utc_now()
            run.status = "success"
            run.summary = (
                f"Processed {len(summary.symbols_processed)} symbols, "
                f"{summary.orders_executed} executed, "
                f"{summary.decisions_rejected} rejected; equity=${summary.snapshot.equity:,.2f}"
            )
            self._repo.record_scheduler_run(run)
        except Exception as exc:
            logger.exception("Scheduled market trading cycle failed: %s", exc)
            run.finished_at = utc_now()
            run.status = "error"
            run.summary = f"{type(exc).__name__}: {exc}"
            self._repo.record_scheduler_run(run)

    async def run_reflection_job(self) -> None:
        run = SchedulerRunRecord(job_name=self.REFLECTION_JOB_ID, status="running")
        self._repo.record_scheduler_run(run)
        try:
            report = await self._orchestrator.run_weekly_reflection(window_days=7)
            run.finished_at = utc_now()
            run.status = "success"
            run.summary = (
                f"Reflection v{report.updated_weights.version}: "
                f"alpha={report.alpha_vs_spy_pct * 100:+.2f}%, "
                f"fallback={report.fallback_used}"
            )
            self._repo.record_scheduler_run(run)
        except Exception as exc:
            logger.exception("Scheduled weekend reflection failed: %s", exc)
            run.finished_at = utc_now()
            run.status = "error"
            run.summary = f"{type(exc).__name__}: {exc}"
            self._repo.record_scheduler_run(run)

    def status(self) -> dict[str, Any]:
        running = bool(self._scheduler and self._scheduler.running)
        jobs_info: list[dict[str, Any]] = []
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                next_run = getattr(job, "next_run_time", None)
                jobs_info.append(
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": next_run.isoformat() if next_run else None,
                    }
                )
        return {
            "enabled": self._settings.scheduler_enabled,
            "running": running,
            "timezone": self._settings.scheduler_timezone,
            "market_cron": self._settings.scheduler_market_cron,
            "reflection_cron": self._settings.scheduler_reflection_cron,
            "jobs": jobs_info,
        }
