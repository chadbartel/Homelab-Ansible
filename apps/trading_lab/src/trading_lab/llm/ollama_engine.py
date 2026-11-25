"""Ollama-backed LLM thesis engine with Qwen3 fast JSON mode and safe HOLD fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from trading_lab.domain.models import (
    HeuristicWeights,
    NewsArticle,
    PositionRecord,
    TechnicalIndicators,
    TradeAction,
    TradeThesis,
)
from trading_lab.interfaces.contracts import LLMThesisEngine

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Robustly extract a JSON object from direct JSON, fenced markdown, or wrapped prose."""
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty LLM response")

    # 1. Direct JSON parse.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2. Markdown code fence extraction.
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        parsed = json.loads(fence_match.group(1))
        if isinstance(parsed, dict):
            return parsed

    # 3. Balanced braces scan from first '{'.
    start = text.find("{")
    if start != -1:
        depth = 0
        in_str = False
        escape = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if not in_str:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : idx + 1]
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                        break

    raise ValueError("No valid JSON object found in LLM response")


class OllamaThesisEngine(LLMThesisEngine):
    """Calls Ollama /api/chat with format='json' and think=false for fast structured JSON."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        default_stop_loss_pct: float = 0.03,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.default_stop_loss_pct = default_stop_loss_pct
        self._transport = transport

    def _build_chat_payload(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": 0.2},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

    async def _post_chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = self._build_chat_payload(system_prompt, user_prompt)
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        ) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        message = data.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("Ollama response missing message.content string")
        return content

    async def generate_thesis(
        self,
        indicators: TechnicalIndicators,
        news: list[NewsArticle],
        heuristics: HeuristicWeights,
        current_position: PositionRecord | None = None,
    ) -> TradeThesis:
        system_prompt = (
            "You are a disciplined quantitative paper-trading research assistant. "
            "Never recompute indicators—rely strictly on the deterministic numbers provided. "
            "Respect the active heuristic weights and return ONLY a single valid JSON object "
            "matching this schema:\n"
            "{\n"
            '  "action": "BUY" | "SELL" | "HOLD",\n'
            '  "confidence": float between 0.0 and 1.0,\n'
            '  "sentiment_score": float between -1.0 and 1.0,\n'
            '  "target_position_pct": float between 0.01 and 0.05,\n'
            '  "stop_loss_pct": float between 0.01 and 0.10,\n'
            '  "catalyst_summary": "short 1-sentence news catalyst summary",\n'
            '  "rationale": "concise 1-2 sentence synthesis of indicators, news, and heuristics"\n'
            "}"
        )
        headlines = [
            {
                "title": item.title,
                "source": item.source,
                "summary": item.summary[:240],
            }
            for item in news[:5]
        ]
        user_context = {
            "symbol": indicators.symbol,
            "deterministic_indicators": indicators.model_dump(mode="json"),
            "active_heuristics": {
                "version": heuristics.version,
                "weights": heuristics.weight_map(),
                "notes": heuristics.notes,
            },
            "current_position": (
                {
                    "quantity": current_position.quantity,
                    "avg_entry_price": current_position.avg_entry_price,
                    "market_price": current_position.market_price,
                    "unrealized_pnl_pct": current_position.unrealized_pnl_pct,
                    "stop_loss_price": current_position.stop_loss_price,
                }
                if current_position
                else None
            ),
            "recent_news": headlines,
        }
        user_prompt = json.dumps(user_context, indent=2)

        raw_content: str | None = None
        try:
            raw_content = await self._post_chat(system_prompt, user_prompt)
            parsed = extract_json_object(raw_content)
            return self._parse_thesis(
                parsed=parsed,
                symbol=indicators.symbol,
                heuristics_version=heuristics.version,
                raw_content=raw_content,
            )
        except Exception as exc:
            logger.warning(
                "Ollama thesis generation failed for %s (%s); using safe HOLD fallback",
                indicators.symbol,
                exc,
            )
            return TradeThesis(
                symbol=indicators.symbol,
                action=TradeAction.HOLD,
                confidence=0.0,
                sentiment_score=0.0,
                target_position_pct=0.0,
                stop_loss_pct=self.default_stop_loss_pct,
                catalyst_summary="LLM unavailable or unparseable response; defaulted to safe HOLD.",
                rationale=f"Fallback triggered: {type(exc).__name__}: {exc}",
                model_name=self.model,
                heuristics_version=heuristics.version,
                fallback_used=True,
                raw_response=raw_content,
            )

    def _parse_thesis(
        self,
        *,
        parsed: dict[str, Any],
        symbol: str,
        heuristics_version: int,
        raw_content: str,
    ) -> TradeThesis:
        raw_action = str(parsed.get("action", "")).strip().upper()
        if raw_action not in {a.value for a in TradeAction}:
            raise ValueError(f"Invalid action returned by LLM: {raw_action!r}")
        action = TradeAction(raw_action)

        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
        sentiment_score = max(-1.0, min(1.0, float(parsed.get("sentiment_score", 0.0))))
        target_position_pct = max(
            0.0, min(1.0, float(parsed.get("target_position_pct", 0.03)))
        )

        raw_stop = parsed.get("stop_loss_pct")
        if raw_stop is None:
            stop_loss_pct = self.default_stop_loss_pct if action == TradeAction.BUY else None
        else:
            stop_loss_pct = float(raw_stop)

        catalyst_summary = str(
            parsed.get("catalyst_summary") or "No distinct catalyst noted."
        ).strip()[:300]
        rationale = str(
            parsed.get("rationale") or "Structured thesis generated from indicators and news."
        ).strip()[:600]

        return TradeThesis(
            symbol=symbol.upper(),
            action=action,
            confidence=round(confidence, 4),
            sentiment_score=round(sentiment_score, 4),
            target_position_pct=round(target_position_pct, 4),
            stop_loss_pct=stop_loss_pct,
            catalyst_summary=catalyst_summary,
            rationale=rationale,
            model_name=self.model,
            heuristics_version=heuristics_version,
            fallback_used=False,
            raw_response=raw_content,
        )

    async def generate_reflection(
        self, context: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        system_prompt = (
            "You are a quantitative trading lab post-mortem analyst. "
            "Review trailing portfolio performance vs SPY, execution activity, and RiskGate "
            "rejections. Return ONLY a JSON object with this schema:\n"
            "{\n"
            '  "summary": "2-3 sentence performance post-mortem vs SPY",\n'
            '  "lessons_learned": ["concise bullet 1", "concise bullet 2"],\n'
            '  "notes": "short description of the weight adjustment",\n'
            '  "suggested_weights": {\n'
            '    "momentum_weight": float,\n'
            '    "trend_weight": float,\n'
            '    "mean_reversion_weight": float,\n'
            '    "news_sentiment_weight": float,\n'
            '    "volatility_penalty_weight": float\n'
            "  }\n"
            "}"
        )
        user_prompt = json.dumps(context, indent=2)
        try:
            raw_content = await self._post_chat(system_prompt, user_prompt)
            parsed = extract_json_object(raw_content)
            return parsed, False
        except Exception as exc:
            logger.warning("Ollama reflection failed (%s); using deterministic fallback", exc)
            prev_weights = context.get("current_weights", {})
            return (
                {
                    "summary": (
                        f"Fallback reflection executed due to LLM error ({type(exc).__name__}). "
                        "Retaining conservative baseline heuristic weights."
                    ),
                    "lessons_learned": [
                        "Preserve deterministic risk-gate discipline during LLM outages.",
                        "Continue benchmarking paper equity against SPY buy-and-hold.",
                    ],
                    "notes": "Fallback deterministic weight preservation",
                    "suggested_weights": prev_weights,
                },
                True,
            )

    async def check_health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0, transport=self._transport) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            available = any(
                m == self.model or m.startswith(self.model.split(":")[0]) for m in models
            )
            return {
                "status": "ok",
                "base_url": self.base_url,
                "model": self.model,
                "model_available": available,
                "installed_models_count": len(models),
            }
        except Exception as exc:
            return {
                "status": "unreachable",
                "base_url": self.base_url,
                "model": self.model,
                "model_available": False,
                "error": str(exc),
            }
