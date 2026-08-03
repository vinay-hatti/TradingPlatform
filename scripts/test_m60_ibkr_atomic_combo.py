from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from trading_ai.broker.ibkr.order_models import (
    IbkrPaperComboLegRequest,
    IbkrPaperComboOrderRequest,
)
from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport
from trading_ai.execution_workspace.service import ExecutionWorkspaceService


def install_fake_ibapi() -> None:
    contract_module = types.ModuleType("ibapi.contract")
    order_module = types.ModuleType("ibapi.order")

    class Contract:
        pass

    class ComboLeg:
        pass

    class Order:
        pass

    contract_module.Contract = Contract
    contract_module.ComboLeg = ComboLeg
    order_module.Order = Order
    sys.modules["ibapi.contract"] = contract_module
    sys.modules["ibapi.order"] = order_module


class FakeApp:
    def __init__(self) -> None:
        self.placed = []
        self.next_id = 71

    def isConnected(self) -> bool:
        return True

    def reserve_order_id(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value

    def placeOrder(self, order_id, contract, order) -> None:
        self.placed.append((order_id, contract, order))


def main() -> None:
    legs = (
        IbkrPaperComboLegRequest(contract_id=101, ratio=1, action="BUY", exchange="SMART"),
        IbkrPaperComboLegRequest(contract_id=202, ratio=1, action="SELL", exchange="SMART"),
    )
    request = IbkrPaperComboOrderRequest(
        aggregate_id="M60-COMBO-1",
        client_order_id="M60-CLIENT-1",
        portfolio_id="PAPER-PRIMARY",
        broker_account_id="DU123",
        symbol="JNJ",
        quantity=1,
        combo_legs=legs,
        limit_price=3.0,
    )
    request.validate()

    install_fake_ibapi()
    transport = IbapiPaperOrderTransport()
    transport._app = FakeApp()
    order_id = transport.submit_combo_order(request)
    assert order_id == 71
    _, contract, order = transport._app.placed[0]
    assert contract.secType == "BAG"
    assert contract.symbol == "JNJ"
    assert len(contract.comboLegs) == 2
    assert contract.comboLegs[0].conId == 101
    assert contract.comboLegs[0].action == "BUY"
    assert contract.comboLegs[1].conId == 202
    assert contract.comboLegs[1].action == "SELL"
    assert float(order.lmtPrice) == 3.0
    assert order.action == "BUY"

    trade_legs = [
        {"side": "BUY", "quantity": 1, "limit_price": 5.0},
        {"side": "SELL", "quantity": 1, "limit_price": 2.0},
    ]
    assert ExecutionWorkspaceService._combo_quantity(trade_legs) == 1.0
    assert ExecutionWorkspaceService._signed_combo_price(trade_legs) == 3.0

    ratio_legs = [
        {"side": "BUY", "quantity": 2, "limit_price": 4.0},
        {"side": "SELL", "quantity": 1, "limit_price": 1.5},
    ]
    assert ExecutionWorkspaceService._combo_quantity(ratio_legs) == 1.0
    assert ExecutionWorkspaceService._signed_combo_price(ratio_legs) == 6.5

    try:
        IbkrPaperComboOrderRequest(
            aggregate_id="BAD",
            client_order_id="BAD",
            portfolio_id="PAPER-PRIMARY",
            broker_account_id="DU123",
            symbol="JNJ",
            quantity=1,
            combo_legs=(legs[0],),
            limit_price=3.0,
        ).validate()
    except ValueError:
        pass
    else:
        raise AssertionError("single-leg BAG request was accepted")

    print("Milestone 60 IBKR atomic combo assertions passed.")


if __name__ == "__main__":
    main()
