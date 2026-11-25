"""Weekly post-mortem reflection service benchmarking portfolio against SPY."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from pathlib import Path

from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import HeuristicWeights, ReflectionReport, new_id, utc_now
from trading_lab.interfaces.contracts import (
    LLMThesisEngine,
    ReflectionService,
    TradeLedgerRepository,
)

logger = logging.getLogger(__name__)


class WeeklyReflectionService(ReflectionService):
    """Evaluates trailing return vs SPY, prompts Ollama, clamps weights, and writes artifact."""

    def __init__(
        self,
        settings: TradingLabSettings,
        repository: TradeLedgerRepository,
        llm_engine: LLMThesisEngine,
    ) -> None:
        self._settings = settings
        self._repo = repository
        self._llm = llm_engine

    async def run_weekly_reflection(self, window_days: int = 7) -> ReflectionReport:
        now = utc_now()
        cutoff = now - timedelta(days=window_days)

        snapshots = self._repo.list_snapshots(limit=500)
        window_snaps = [s for s in snapshots if s.timestamp >= cutoff]
        if len(window_snaps) < 2:
            window_snaps = snapshots[-2:] if len(snapshots) >= 2 else snapshots

        if len(window_snaps) >= 2:
            first, last = window_snaps[0], window_snaps[-1]
            portfolio_return = (
                (last.equity - first.equity) / first.equity if first.equity > 0 else 0.0
            )
            spy_return = (
                (last.spy_price - first.spy_price) / first.spy_price
                if first.spy_price > 0
                else 0.0
            )
        elif len(window_snaps) == 1:
            only = window_snaps[0]
            portfolio_return = (only.equity / self._settings.initial_cash) - 1.0
            spy_return = (only.spy_benchmark_equity / self._settings.initial_cash) - 1.0
        else:
            portfolio_return = 0.0
            spy_return = 0.0

        alpha_vs_spy = round(portfolio_return - spy_return, 6)

        theses = [t for t in self._repo.list_theses(limit=500) if t.created_at >= cutoff]
        executions = [
            e for e in self._repo.list_executions(limit=500) if e.executed_at >= cutoff
        ]
        decisions = [
            d for d in self._repo.list_risk_decisions(limit=500) if d.created_at >= cutoff
        ]
        rejections = [
            d for d in decisions if not d.approved and d.rule_code != "HOLD_NO_ACTION"
        ]
        rejection_counts = dict(Counter(d.rule_code for d in rejections))

        previous_weights = self._repo.get_latest_heuristics()

        context = {
            "window_days": window_days,
            "portfolio_return_pct": round(portfolio_return, 6),
            "spy_return_pct": round(spy_return, 6),
            "alpha_vs_spy_pct": alpha_vs_spy,
            "total_theses": len(theses),
            "total_executions": len(executions),
            "total_rejections": len(rejections),
            "rejection_breakdown": rejection_counts,
            "current_heuristics_version": previous_weights.version,
            "current_weights": previous_weights.weight_map(),
        }

        parsed, fallback_used = await self._llm.generate_reflection(context)

        raw_suggested = parsed.get("suggested_weights")
        if not isinstance(raw_suggested, dict):
            raw_suggested = previous_weights.weight_map()

        notes = str(
            parsed.get("notes") or f"Weekly reflection v{previous_weights.version + 1}"
        ).strip()[:300]

        updated_weights = HeuristicWeights.clamp_and_normalize(
            raw_suggested,
            version=previous_weights.version + 1,
            notes=notes,
            min_weight=0.05,
            max_weight=0.70,
        )
        self._repo.save_heuristics(updated_weights)

        raw_lessons = parsed.get("lessons_learned")
        if isinstance(raw_lessons, list):
            lessons = [str(item).strip() for item in raw_lessons if str(item).strip()][:6]
        else:
            lessons = ["Maintain strict deterministic risk discipline."]
        if not lessons:
            lessons = ["Maintain strict deterministic risk discipline."]

        summary = str(
            parsed.get("summary")
            or f"Portfolio returned {portfolio_return * 100:+.2f}% vs SPY {spy_return * 100:+.2f}%."
        ).strip()[:1000]

        report_id = new_id()
        artifact_path = self._write_artifact(
            report_id=report_id,
            now=now,
            report_payload={
                "id": report_id,
                "created_at": now.isoformat(),
                "window_days": window_days,
                "portfolio_return_pct": round(portfolio_return, 6),
                "spy_return_pct": round(spy_return, 6),
                "alpha_vs_spy_pct": alpha_vs_spy,
                "total_theses": len(theses),
                "total_executions": len(executions),
                "total_rejections": len(rejections),
                "rejection_breakdown": rejection_counts,
                "summary": summary,
                "lessons_learned": lessons,
                "previous_weights": previous_weights.model_dump(mode="json"),
                "updated_weights": updated_weights.model_dump(mode="json"),
                "model_name": self._settings.ollama_model,
                "fallback_used": fallback_used,
            },
        )

        report = ReflectionReport(
            id=report_id,
            created_at=now,
            window_days=window_days,
            portfolio_return_pct=round(portfolio_return, 6),
            spy_return_pct=round(spy_return, 6),
            alpha_vs_spy_pct=alpha_vs_spy,
            total_theses=len(theses),
            total_executions=len(executions),
            total_rejections=len(rejections),
            summary=summary,
            lessons_learned=lessons,
            previous_weights=previous_weights,
            updated_weights=updated_weights,
            artifact_path=artifact_path,
            model_name=self._settings.ollama_model,
            fallback_used=fallback_used,
        )
        self._repo.save_reflection(report)
        return report

    def _write_artifact(
        self, *, report_id: str, now, report_payload: dict
    ) -> str | None:
        import json

        try:
            artifacts_dir = Path(self._settings.artifacts_dir)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            filename = f"reflection_{now.strftime('%Y%m%dT%H%M%SZ')}_{report_id[:8]}.json"
            target = artifacts_dir / filename
            target.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
            return str(target)
        except Exception as exc:
            logger.warning("Failed to write reflection artifact: %s", exc)
            return None
