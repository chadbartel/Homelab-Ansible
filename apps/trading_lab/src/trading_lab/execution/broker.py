"""Paper-only broker executors: Alpaca Paper API and internal Virtual Ledger."""

from __future__ import annotations

import asyncio
import logging

from trading_lab.config import TradingLabSettings
from trading_lab.domain.models import (
    OrderExecution,
    OrderRequest,
    PositionRecord,
    TradeAction,
    new_id,
    utc_now,
)
from trading_lab.interfaces.contracts import BrokerExecutor, TradeLedgerRepository
from trading_lab.risk.gate import (
    PaperOnlyViolationError,
    is_valid_alpaca_paper_url,
    validate_paper_only_config,
)

logger = logging.getLogger(__name__)


class AlpacaPaperBrokerExecutor(BrokerExecutor):
    """Executes paper orders via alpaca-py TradingClient with strict paper-only assertions."""

    def __init__(self, settings: TradingLabSettings) -> None:
        self._settings = settings
        violation = validate_paper_only_config(settings, "alpaca_paper")
        if violation:
            raise PaperOnlyViolationError(violation)

    @property
    def mode(self) -> str:
        return "alpaca_paper"

    def _build_client(self):
        from alpaca.trading.client import TradingClient

        violation = validate_paper_only_config(self._settings, "alpaca_paper")
        if violation:
            raise PaperOnlyViolationError(violation)

        client = TradingClient(
            api_key=self._settings.alpaca_api_key,
            secret_key=self._settings.alpaca_secret_key,
            paper=True,
            url_override=self._settings.alpaca_paper_base_url,
        )
        base_url = str(getattr(client, "_base_url", self._settings.alpaca_paper_base_url))
        if not is_valid_alpaca_paper_url(base_url):
            raise PaperOnlyViolationError(
                f"TradingClient resolved non-paper endpoint {base_url!r}; aborting."
            )
        return client

    def _submit_sync(self, order: OrderRequest) -> OrderExecution:
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest, StopLossRequest

        if not order.paper_only:
            raise PaperOnlyViolationError("OrderRequest.paper_only must be True.")

        client = self._build_client()
        side = OrderSide.BUY if order.action == TradeAction.BUY else OrderSide.SELL

        if order.action == TradeAction.BUY and order.stop_loss_price is not None:
            whole_qty = int(order.quantity)
            if whole_qty >= 1:
                req = MarketOrderRequest(
                    symbol=order.symbol.upper(),
                    qty=whole_qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    order_class=OrderClass.OTO,
                    stop_loss=StopLossRequest(stop_price=round(order.stop_loss_price, 2)),
                )
                submitted_qty = float(whole_qty)
            else:
                req = MarketOrderRequest(
                    symbol=order.symbol.upper(),
                    qty=round(order.quantity, 4),
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
                submitted_qty = round(order.quantity, 4)
        else:
            req = MarketOrderRequest(
                symbol=order.symbol.upper(),
                qty=round(order.quantity, 4),
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            submitted_qty = round(order.quantity, 4)

        alpaca_order = client.submit_order(order_data=req)
        filled_price = (
            float(alpaca_order.filled_avg_price)
            if getattr(alpaca_order, "filled_avg_price", None)
            else order.reference_price
        )
        return OrderExecution(
            thesis_id=order.thesis_id,
            risk_decision_id=order.risk_decision_id,
            broker_mode=self.mode,
            broker_order_id=str(getattr(alpaca_order, "id", new_id())),
            symbol=order.symbol.upper(),
            action=order.action,
            quantity=submitted_qty,
            fill_price=round(filled_price, 4),
            notional=round(submitted_qty * filled_price, 4),
            stop_loss_price=order.stop_loss_price,
            status=str(getattr(alpaca_order, "status", "submitted")),
            message="Submitted via Alpaca Paper Trading API.",
        )

    async def execute_order(self, order: OrderRequest) -> OrderExecution:
        return await asyncio.to_thread(self._submit_sync, order)

    def _get_cash_sync(self) -> float:
        client = self._build_client()
        account = client.get_account()
        return float(account.cash)

    async def get_account_cash(self) -> float:
        return await asyncio.to_thread(self._get_cash_sync)

    def _get_positions_sync(self, latest_prices: dict[str, float]) -> list[PositionRecord]:
        client = self._build_client()
        raw_positions = client.get_all_positions()
        records: list[PositionRecord] = []
        for pos in raw_positions:
            sym = str(pos.symbol).upper()
            records.append(
                PositionRecord(
                    symbol=sym,
                    quantity=float(pos.qty),
                    avg_entry_price=float(pos.avg_entry_price),
                    market_price=latest_prices.get(sym, float(pos.current_price)),
                    stop_loss_price=None,
                    updated_at=utc_now(),
                )
            )
        return records

    async def get_positions(self, latest_prices: dict[str, float]) -> list[PositionRecord]:
        return await asyncio.to_thread(self._get_positions_sync, latest_prices)


class VirtualLedgerBrokerExecutor(BrokerExecutor):
    """Internal paper-trading simulator backed directly by TradeLedgerRepository."""

    def __init__(
        self,
        repository: TradeLedgerRepository,
        initial_cash: float = 100000.0,
        paper_only: bool = True,
    ) -> None:
        if not paper_only:
            raise PaperOnlyViolationError("VirtualLedgerBrokerExecutor requires paper_only=True.")
        self._repo = repository
        self._initial_cash = initial_cash

    @property
    def mode(self) -> str:
        return "virtual_ledger"

    async def execute_order(self, order: OrderRequest) -> OrderExecution:
        if not order.paper_only:
            raise PaperOnlyViolationError("OrderRequest.paper_only must be True.")

        sym = order.symbol.upper()
        fill_price = round(float(order.reference_price), 4)
        cash = self._repo.get_cash(self._initial_cash)
        existing = self._repo.get_position(sym)

        if order.action == TradeAction.BUY:
            qty = round(float(order.quantity), 6)
            notional = round(qty * fill_price, 4)
            if notional > cash + 1e-4:
                return OrderExecution(
                    thesis_id=order.thesis_id,
                    risk_decision_id=order.risk_decision_id,
                    broker_mode=self.mode,
                    broker_order_id=f"VL-REJ-{new_id()[:10]}",
                    symbol=sym,
                    action=order.action,
                    quantity=0.0,
                    fill_price=fill_price,
                    notional=0.0,
                    stop_loss_price=order.stop_loss_price,
                    status="rejected",
                    message="Insufficient virtual cash balance.",
                )

            new_cash = round(cash - notional, 4)
            self._repo.set_cash(new_cash)

            if existing and existing.quantity > 0:
                total_qty = round(existing.quantity + qty, 6)
                total_cost = (existing.quantity * existing.avg_entry_price) + notional
                avg_entry = round(total_cost / total_qty, 4)
            else:
                total_qty = qty
                avg_entry = fill_price

            self._repo.upsert_position(
                PositionRecord(
                    symbol=sym,
                    quantity=total_qty,
                    avg_entry_price=avg_entry,
                    market_price=fill_price,
                    stop_loss_price=order.stop_loss_price,
                    updated_at=utc_now(),
                )
            )
            return OrderExecution(
                thesis_id=order.thesis_id,
                risk_decision_id=order.risk_decision_id,
                broker_mode=self.mode,
                broker_order_id=f"VL-{new_id()[:12]}",
                symbol=sym,
                action=TradeAction.BUY,
                quantity=qty,
                fill_price=fill_price,
                notional=notional,
                stop_loss_price=order.stop_loss_price,
                status="filled",
                message=f"Simulated virtual BUY fill at ${fill_price:,.2f}.",
            )

        if order.action == TradeAction.SELL:
            if existing is None or existing.quantity <= 0:
                return OrderExecution(
                    thesis_id=order.thesis_id,
                    risk_decision_id=order.risk_decision_id,
                    broker_mode=self.mode,
                    broker_order_id=f"VL-REJ-{new_id()[:10]}",
                    symbol=sym,
                    action=TradeAction.SELL,
                    quantity=0.0,
                    fill_price=fill_price,
                    notional=0.0,
                    stop_loss_price=None,
                    status="rejected",
                    message="No open position to sell in virtual ledger.",
                )

            sell_qty = round(min(float(order.quantity), existing.quantity), 6)
            notional = round(sell_qty * fill_price, 4)
            self._repo.set_cash(round(cash + notional, 4))

            remaining = round(existing.quantity - sell_qty, 6)
            if remaining <= 1e-6:
                self._repo.delete_position(sym)
            else:
                self._repo.upsert_position(
                    PositionRecord(
                        symbol=sym,
                        quantity=remaining,
                        avg_entry_price=existing.avg_entry_price,
                        market_price=fill_price,
                        stop_loss_price=existing.stop_loss_price,
                        updated_at=utc_now(),
                    )
                )

            return OrderExecution(
                thesis_id=order.thesis_id,
                risk_decision_id=order.risk_decision_id,
                broker_mode=self.mode,
                broker_order_id=f"VL-{new_id()[:12]}",
                symbol=sym,
                action=TradeAction.SELL,
                quantity=sell_qty,
                fill_price=fill_price,
                notional=notional,
                stop_loss_price=None,
                status="filled",
                message=f"Simulated virtual SELL fill at ${fill_price:,.2f}.",
            )

        raise ValueError(f"Unsupported order action for broker execution: {order.action}")

    async def get_account_cash(self) -> float:
        return self._repo.get_cash(self._initial_cash)

    async def get_positions(self, latest_prices: dict[str, float]) -> list[PositionRecord]:
        positions = self._repo.list_positions()
        updated: list[PositionRecord] = []
        for pos in positions:
            price = latest_prices.get(pos.symbol, pos.market_price)
            marked = pos.model_copy(update={"market_price": price, "updated_at": utc_now()})
            self._repo.upsert_position(marked)
            updated.append(marked)
        return updated


def build_broker_executor(
    settings: TradingLabSettings,
    repository: TradeLedgerRepository,
) -> BrokerExecutor:
    """Select Alpaca Paper broker when credentials exist; otherwise Virtual Ledger."""
    if settings.alpaca_configured:
        logger.info("Using AlpacaPaperBrokerExecutor (paper-api.alpaca.markets)")
        return AlpacaPaperBrokerExecutor(settings)
    logger.info("Alpaca keys not configured; using VirtualLedgerBrokerExecutor")
    return VirtualLedgerBrokerExecutor(
        repository=repository,
        initial_cash=settings.initial_cash,
        paper_only=settings.paper_only,
    )
