"""Unit tests for hard-coded DeterministicRiskGate guardrails."""

from __future__ import annotations

import pytest

from tests.conftest import make_thesis
from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import PositionRecord, TradeAction
from trading_lab.execution.broker import AlpacaPaperBrokerExecutor
from trading_lab.risk.gate import DeterministicRiskGate, PaperOnlyViolationError


def test_approves_valid_buy_order(settings, sample_indicators, sample_snapshot) -> None:
    gate = DeterministicRiskGate(settings)
    thesis = make_thesis(
        symbol="AAPL",
        action=TradeAction.BUY,
        confidence=0.80,
        target_position_pct=0.04,
        stop_loss_pct=0.03,
    )

    decision = gate.evaluate(
        thesis=thesis,
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="virtual_ledger",
    )

    assert decision.approved is True
    assert decision.rule_code == "APPROVED"
    assert decision.requested_notional == pytest.approx(4000.0, abs=1e-2)
    assert decision.approved_quantity == pytest.approx(20.0, abs=1e-4)
    assert decision.approved_stop_loss_price == pytest.approx(194.0, abs=1e-2)
    assert decision.approved_stop_loss_price < sample_indicators.latest_close


def test_rejects_oversized_single_position_over_5_pct(
    settings, sample_indicators, sample_snapshot
) -> None:
    gate = DeterministicRiskGate(settings)
    thesis = make_thesis(target_position_pct=0.06, stop_loss_pct=0.03)

    decision = gate.evaluate(
        thesis=thesis,
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="virtual_ledger",
    )

    assert decision.approved is False
    assert decision.rule_code == "RULE_MAX_POSITION_CAP"


def test_rejects_cumulative_position_cap_breach(
    settings, sample_indicators, sample_snapshot
) -> None:
    gate = DeterministicRiskGate(settings)
    existing = PositionRecord(
        symbol="AAPL",
        quantity=15.0,  # 15 * $200 = $3,000 (3% of $100k)
        avg_entry_price=195.0,
        market_price=200.0,
        stop_loss_price=189.0,
    )
    thesis = make_thesis(target_position_pct=0.03, stop_loss_pct=0.03)  # +3% => 6% > 5%

    decision = gate.evaluate(
        thesis=thesis,
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=existing,
        broker_mode="virtual_ledger",
    )

    assert decision.approved is False
    assert decision.rule_code == "RULE_MAX_POSITION_CAP"


def test_rejects_buy_when_daily_drawdown_killswitch_triggered(
    settings, sample_indicators, sample_snapshot
) -> None:
    gate = DeterministicRiskGate(settings)
    drawdown_snap = sample_snapshot.model_copy(update={"daily_drawdown_pct": 0.035})
    thesis = make_thesis(target_position_pct=0.03, stop_loss_pct=0.03)

    decision = gate.evaluate(
        thesis=thesis,
        indicators=sample_indicators,
        snapshot=drawdown_snap,
        current_position=None,
        broker_mode="virtual_ledger",
    )

    assert decision.approved is False
    assert decision.rule_code == "RULE_DAILY_DRAWDOWN_KILLSWITCH"


def test_rejects_disallowed_ticker(settings, sample_indicators, sample_snapshot) -> None:
    gate = DeterministicRiskGate(settings)
    thesis = make_thesis(symbol="GME", target_position_pct=0.02, stop_loss_pct=0.03)

    decision = gate.evaluate(
        thesis=thesis,
        indicators=sample_indicators.model_copy(update={"symbol": "GME"}),
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="virtual_ledger",
    )

    assert decision.approved is False
    assert decision.rule_code == "RULE_TICKER_NOT_ALLOWED"


@pytest.mark.parametrize("bad_stop", [None, 0.001, 0.25])
def test_rejects_missing_or_invalid_stop_loss(
    settings, sample_indicators, sample_snapshot, bad_stop
) -> None:
    gate = DeterministicRiskGate(settings)
    thesis = make_thesis(target_position_pct=0.03, stop_loss_pct=bad_stop)

    decision = gate.evaluate(
        thesis=thesis,
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="virtual_ledger",
    )

    assert decision.approved is False
    assert decision.rule_code == "RULE_MISSING_OR_INVALID_STOP_LOSS"


def test_rejects_paper_only_disabled_and_live_alpaca_url(
    sample_indicators, sample_snapshot
) -> None:
    live_flag_settings = TradingLabSettings(paper_only=False)
    gate_flag = DeterministicRiskGate(live_flag_settings)
    res_flag = gate_flag.evaluate(
        thesis=make_thesis(),
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="virtual_ledger",
    )
    assert res_flag.approved is False
    assert res_flag.rule_code == "RULE_PAPER_ONLY_VIOLATION"

    live_url_settings = TradingLabSettings(
        paper_only=True,
        alpaca_api_key="PKTEST",
        alpaca_secret_key="SKTEST",
        alpaca_paper_base_url="https://api.alpaca.markets",
    )
    gate_url = DeterministicRiskGate(live_url_settings)
    res_url = gate_url.evaluate(
        thesis=make_thesis(),
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="alpaca_paper",
    )
    assert res_url.approved is False
    assert res_url.rule_code == "RULE_PAPER_ONLY_VIOLATION"

    with pytest.raises(PaperOnlyViolationError):
        AlpacaPaperBrokerExecutor(live_url_settings)


def test_rejects_low_confidence_and_insufficient_cash(
    settings, sample_indicators, sample_snapshot
) -> None:
    gate = DeterministicRiskGate(settings)

    low_conf = gate.evaluate(
        thesis=make_thesis(confidence=0.40),
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="virtual_ledger",
    )
    assert low_conf.approved is False
    assert low_conf.rule_code == "RULE_LOW_CONFIDENCE"

    low_cash_snap = sample_snapshot.model_copy(update={"cash": 1000.0})
    no_cash = gate.evaluate(
        thesis=make_thesis(target_position_pct=0.04, confidence=0.80),
        indicators=sample_indicators,
        snapshot=low_cash_snap,
        current_position=None,
        broker_mode="virtual_ledger",
    )
    assert no_cash.approved is False
    assert no_cash.rule_code == "RULE_INSUFFICIENT_CASH"


def test_hold_and_sell_evaluations(settings, sample_indicators, sample_snapshot) -> None:
    gate = DeterministicRiskGate(settings)

    hold_res = gate.evaluate(
        thesis=make_thesis(action=TradeAction.HOLD),
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="virtual_ledger",
    )
    assert hold_res.approved is False
    assert hold_res.rule_code == "HOLD_NO_ACTION"

    sell_no_pos = gate.evaluate(
        thesis=make_thesis(action=TradeAction.SELL, confidence=0.80),
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=None,
        broker_mode="virtual_ledger",
    )
    assert sell_no_pos.approved is False
    assert sell_no_pos.rule_code == "RULE_NO_OPEN_POSITION"

    open_pos = PositionRecord(
        symbol="AAPL",
        quantity=12.0,
        avg_entry_price=190.0,
        market_price=200.0,
        stop_loss_price=184.0,
    )
    sell_ok = gate.evaluate(
        thesis=make_thesis(action=TradeAction.SELL, confidence=0.80),
        indicators=sample_indicators,
        snapshot=sample_snapshot,
        current_position=open_pos,
        broker_mode="virtual_ledger",
    )
    assert sell_ok.approved is True
    assert sell_ok.rule_code == "APPROVED"
    assert sell_ok.approved_quantity == pytest.approx(12.0)
