"""Unit tests for OllamaThesisEngine JSON parsing, Qwen3 payload, and safe fallbacks."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from tests.conftest import make_mock_ollama_transport
from trading_lab.domain.models import HeuristicWeights, TradeAction
from trading_lab.llm.ollama_engine import OllamaThesisEngine, extract_json_object


@pytest.mark.asyncio
async def test_valid_json_and_qwen3_payload_verification(
    sample_indicators, sample_news
) -> None:
    captured_payloads: list[dict[str, Any]] = []
    heuristics = HeuristicWeights(version=3, momentum_weight=0.40, notes="v3 boosted momentum")

    def chat_handler(body: dict[str, Any]) -> httpx.Response:
        captured_payloads.append(body)
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "action": "BUY",
                            "confidence": 0.78,
                            "sentiment_score": 0.55,
                            "target_position_pct": 0.04,
                            "stop_loss_pct": 0.03,
                            "catalyst_summary": "Enterprise AI expansion.",
                            "rationale": "Bullish EMA crossover with positive news.",
                        }
                    ),
                }
            },
        )

    engine = OllamaThesisEngine(
        base_url="http://mock-ollama:11434",
        model="huihui_ai/qwen3-abliterated:8b-v2",
        transport=make_mock_ollama_transport(chat_handler),
    )

    thesis = await engine.generate_thesis(sample_indicators, sample_news, heuristics)

    assert thesis.action == TradeAction.BUY
    assert thesis.confidence == pytest.approx(0.78)
    assert thesis.stop_loss_pct == pytest.approx(0.03)
    assert thesis.fallback_used is False
    assert thesis.heuristics_version == 3

    assert len(captured_payloads) == 1
    sent = captured_payloads[0]
    assert sent["model"] == "huihui_ai/qwen3-abliterated:8b-v2"
    assert sent["stream"] is False
    assert sent["format"] == "json"
    assert sent["think"] is False
    assert sent["options"]["temperature"] == pytest.approx(0.2)
    user_payload = json.loads(sent["messages"][-1]["content"])
    assert user_payload["active_heuristics"]["version"] == 3
    assert user_payload["active_heuristics"]["weights"]["momentum_weight"] == pytest.approx(0.40)
    assert user_payload["deterministic_indicators"]["rsi_14"] == pytest.approx(58.5)


@pytest.mark.asyncio
async def test_fenced_and_prose_json_extraction(
    sample_indicators, sample_news, sample_heuristics
) -> None:
    fenced = (
        "Here is my analysis:\n```json\n"
        '{"action": "sell", "confidence": 0.72, "sentiment_score": -0.4, '
        '"target_position_pct": 0.03, "stop_loss_pct": 0.03, '
        '"catalyst_summary": "Margin pressure", "rationale": "Trend weakening."}\n'
        "```"
    )
    assert extract_json_object(fenced)["action"] == "sell"

    def chat_handler(_body: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": fenced}})

    engine = OllamaThesisEngine(
        base_url="http://mock-ollama:11434",
        model="huihui_ai/qwen3-abliterated:8b-v2",
        transport=make_mock_ollama_transport(chat_handler),
    )

    thesis = await engine.generate_thesis(sample_indicators, sample_news, sample_heuristics)
    assert thesis.action == TradeAction.SELL
    assert thesis.fallback_used is False


@pytest.mark.asyncio
async def test_malformed_json_falls_back_to_safe_hold(
    sample_indicators, sample_news, sample_heuristics
) -> None:
    def chat_handler(_body: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "NOT VALID JSON AT ALL"}},
        )

    engine = OllamaThesisEngine(
        base_url="http://mock-ollama:11434",
        model="huihui_ai/qwen3-abliterated:8b-v2",
        transport=make_mock_ollama_transport(chat_handler),
    )

    thesis = await engine.generate_thesis(sample_indicators, sample_news, sample_heuristics)
    assert thesis.action == TradeAction.HOLD
    assert thesis.confidence == 0.0
    assert thesis.fallback_used is True


@pytest.mark.asyncio
async def test_http_timeout_and_error_fall_back_to_safe_hold(
    sample_indicators, sample_news, sample_heuristics
) -> None:
    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Ollama timed out", request=request)

    engine = OllamaThesisEngine(
        base_url="http://mock-ollama:11434",
        model="huihui_ai/qwen3-abliterated:8b-v2",
        transport=httpx.MockTransport(failing_handler),
    )

    thesis = await engine.generate_thesis(sample_indicators, sample_news, sample_heuristics)
    assert thesis.action == TradeAction.HOLD
    assert thesis.fallback_used is True

    health = await engine.check_health()
    assert health["status"] == "unreachable"
    assert health["model_available"] is False


@pytest.mark.asyncio
async def test_ollama_health_check_ok() -> None:
    engine = OllamaThesisEngine(
        base_url="http://mock-ollama:11434",
        model="huihui_ai/qwen3-abliterated:8b-v2",
        transport=make_mock_ollama_transport(
            lambda _b: httpx.Response(200, json={"message": {"content": "{}"}}),
            models=["huihui_ai/qwen3-abliterated:8b-v2", "llama3.1:8b"],
        ),
    )
    health = await engine.check_health()
    assert health["status"] == "ok"
    assert health["model_available"] is True
    assert health["installed_models_count"] == 2


@pytest.mark.asyncio
async def test_prose_with_leading_braces_and_strict_tag_health_check() -> None:
    wrapped = (
        'Note {disclaimer: paper mode}: '
        '{"action": "BUY", "confidence": 0.75, "sentiment_score": 0.4, '
        '"target_position_pct": 0.03, "stop_loss_pct": 0.03, '
        '"catalyst_summary": "Steady growth", "rationale": "Trend intact"}'
    )
    extracted = extract_json_object(wrapped)
    assert extracted["action"] == "BUY"

    engine = OllamaThesisEngine(
        base_url="http://mock-ollama:11434",
        model="huihui_ai/qwen3-abliterated:8b-v2",
        transport=make_mock_ollama_transport(
            lambda _b: httpx.Response(200, json={"message": {"content": "{}"}}),
            models=["huihui_ai/qwen3-abliterated:32b"],
        ),
    )
    health = await engine.check_health()
    assert health["status"] == "ok"
    assert health["model_available"] is False
