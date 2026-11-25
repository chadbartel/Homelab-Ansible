"""Hard-coded deterministic financial RiskGate (NEVER overridden by LLM)."""

from __future__ import annotations

from urllib.parse import urlparse

from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import (
    PortfolioSnapshot,
    PositionRecord,
    RiskDecision,
    TechnicalIndicators,
    TradeAction,
    TradeThesis,
)
from trading_lab.interfaces.contracts import RiskGate


class PaperOnlyViolationError(RuntimeError):
    """Raised when configuration attempts to route orders outside paper trading."""


def validate_paper_only_config(settings: TradingLabSettings, broker_mode: str) -> str | None:
    """Return violation message if paper-only invariants are broken, else None."""
    if not settings.paper_only:
        return "PAPER_ONLY must be True; live trading is strictly prohibited."

    if broker_mode == "alpaca_paper":
        url = settings.alpaca_paper_base_url.strip().lower()
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        if "paper-api.alpaca.markets" not in host or host == "api.alpaca.markets":
            return (
                f"Alpaca base URL {settings.alpaca_paper_base_url!r} violates paper-only "
                "guardrail (must target paper-api.alpaca.markets)."
            )
    return None


class DeterministicRiskGate(RiskGate):
    """Evaluates LLM proposals against immutable deterministic safety rules."""

    def __init__(self, settings: TradingLabSettings) -> None:
        self._settings = settings

    def evaluate(
        self,
        thesis: TradeThesis,
        indicators: TechnicalIndicators,
        snapshot: PortfolioSnapshot,
        current_position: PositionRecord | None,
        broker_mode: str,
    ) -> RiskDecision:
        symbol = thesis.symbol.upper()
        equity = float(snapshot.equity)
        drawdown = float(snapshot.daily_drawdown_pct)

        # 1. Paper-only assertion (non-negotiable).
        paper_violation = validate_paper_only_config(self._settings, broker_mode)
        if paper_violation:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=thesis.action,
                approved=False,
                rule_code="RULE_PAPER_ONLY_VIOLATION",
                reason=paper_violation,
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        # 2. Ticker allowlist enforcement.
        if symbol not in self._settings.allowlist_symbols:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=thesis.action,
                approved=False,
                rule_code="RULE_TICKER_NOT_ALLOWED",
                reason=f"Symbol {symbol} is outside configured allowlist.",
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        # 3. HOLD requires no execution.
        if thesis.action == TradeAction.HOLD:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=TradeAction.HOLD,
                approved=False,
                rule_code="HOLD_NO_ACTION",
                reason="Thesis action is HOLD; no order submitted.",
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        # 4. Minimum confidence threshold.
        if thesis.confidence < self._settings.min_confidence:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=thesis.action,
                approved=False,
                rule_code="RULE_LOW_CONFIDENCE",
                reason=(
                    f"Thesis confidence {thesis.confidence:.2f} is below minimum "
                    f"threshold {self._settings.min_confidence:.2f}."
                ),
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        entry_price = float(indicators.latest_close)
        if entry_price <= 0:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=thesis.action,
                approved=False,
                rule_code="RULE_INVALID_PRICE",
                reason=f"Invalid reference price {entry_price} for {symbol}.",
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        # 5. SELL evaluation (requires open position).
        if thesis.action == TradeAction.SELL:
            if current_position is None or current_position.quantity <= 0:
                return RiskDecision(
                    thesis_id=thesis.id,
                    symbol=symbol,
                    requested_action=TradeAction.SELL,
                    approved=False,
                    rule_code="RULE_NO_OPEN_POSITION",
                    reason=f"Cannot SELL {symbol}; no open position exists.",
                    portfolio_equity=equity,
                    daily_drawdown_pct=drawdown,
                )
            sell_notional = round(current_position.quantity * entry_price, 4)
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=TradeAction.SELL,
                approved=True,
                rule_code="APPROVED",
                reason=f"Approved full exit of {current_position.quantity:.4f} shares of {symbol}.",
                requested_notional=sell_notional,
                approved_quantity=current_position.quantity,
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        # 6. BUY evaluation: Daily drawdown kill-switch.
        if drawdown >= self._settings.daily_drawdown_limit_pct:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=TradeAction.BUY,
                approved=False,
                rule_code="RULE_DAILY_DRAWDOWN_KILLSWITCH",
                reason=(
                    f"Daily drawdown {drawdown * 100:.2f}% reached/exceeded limit "
                    f"{self._settings.daily_drawdown_limit_pct * 100:.2f}%; BUY orders halted."
                ),
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        # 7. BUY evaluation: Mandatory explicit stop-loss within safe bounds.
        stop_pct = thesis.stop_loss_pct
        if (
            stop_pct is None
            or stop_pct < self._settings.min_stop_loss_pct
            or stop_pct > self._settings.max_stop_loss_pct
        ):
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=TradeAction.BUY,
                approved=False,
                rule_code="RULE_MISSING_OR_INVALID_STOP_LOSS",
                reason=(
                    f"BUY requires stop_loss_pct in "
                    f"[{self._settings.min_stop_loss_pct:.3f}, "
                    f"{self._settings.max_stop_loss_pct:.3f}]; got {stop_pct!r}."
                ),
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        stop_loss_price = round(entry_price * (1.0 - stop_pct), 4)
        if stop_loss_price <= 0 or stop_loss_price >= entry_price:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=TradeAction.BUY,
                approved=False,
                rule_code="RULE_MISSING_OR_INVALID_STOP_LOSS",
                reason=(
                    f"Computed stop-loss price {stop_loss_price} must be strictly "
                    f"below entry price {entry_price}."
                ),
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        # 8. BUY evaluation: Hard max 5% single-position cap (order & cumulative).
        if equity <= 0 or thesis.target_position_pct <= 0:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=TradeAction.BUY,
                approved=False,
                rule_code="RULE_INVALID_SIZING",
                reason="Equity and target_position_pct must be strictly positive.",
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        requested_notional = round(equity * thesis.target_position_pct, 4)
        existing_value = (
            current_position.quantity * entry_price if current_position else 0.0
        )
        resulting_value = existing_value + requested_notional
        max_allowed_value = equity * self._settings.max_position_pct

        if (
            thesis.target_position_pct > self._settings.max_position_pct + 1e-9
            or requested_notional > max_allowed_value + 1e-4
            or resulting_value > max_allowed_value + 1e-4
        ):
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=TradeAction.BUY,
                approved=False,
                rule_code="RULE_MAX_POSITION_CAP",
                reason=(
                    f"Requested/resulting position ${resulting_value:,.2f} exceeds "
                    f"{self._settings.max_position_pct * 100:.1f}% equity cap "
                    f"(${max_allowed_value:,.2f})."
                ),
                requested_notional=requested_notional,
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        # 9. BUY evaluation: Available buying power / cash check.
        if requested_notional > snapshot.cash + 1e-4:
            return RiskDecision(
                thesis_id=thesis.id,
                symbol=symbol,
                requested_action=TradeAction.BUY,
                approved=False,
                rule_code="RULE_INSUFFICIENT_CASH",
                reason=(
                    f"Requested notional ${requested_notional:,.2f} exceeds available "
                    f"cash ${snapshot.cash:,.2f}."
                ),
                requested_notional=requested_notional,
                portfolio_equity=equity,
                daily_drawdown_pct=drawdown,
            )

        approved_qty = round(requested_notional / entry_price, 6)
        return RiskDecision(
            thesis_id=thesis.id,
            symbol=symbol,
            requested_action=TradeAction.BUY,
            approved=True,
            rule_code="APPROVED",
            reason=(
                f"Approved BUY {approved_qty:.4f} {symbol} (~${requested_notional:,.2f}) "
                f"with mandatory stop-loss at ${stop_loss_price:,.2f} ({stop_pct * 100:.1f}%)."
            ),
            requested_notional=requested_notional,
            approved_quantity=approved_qty,
            approved_stop_loss_price=stop_loss_price,
            portfolio_equity=equity,
            daily_drawdown_pct=drawdown,
        )
