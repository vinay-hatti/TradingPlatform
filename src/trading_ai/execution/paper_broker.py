import json
from pathlib import Path

from trading_ai.execution.order import PaperOrder
from trading_ai.execution.position import PaperPosition


class PaperBroker:

    def __init__(
        self,
        state_dir="data/paper",
        initial_cash=100000.0,
    ):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.orders_file = self.state_dir / "orders.json"
        self.positions_file = self.state_dir / "positions.json"
        self.cash_file = self.state_dir / "cash.json"

        self.initial_cash = initial_cash

        self.orders = self._load_json(self.orders_file, [])
        self.positions = self._load_json(self.positions_file, [])
        self.cash = self._load_json(
            self.cash_file,
            {"cash": initial_cash},
        )["cash"]

    def has_open_position(self, symbol, signal, strike, expiry):

        for p in self.open_positions():
            if (
                p["symbol"] == symbol
                and p["signal"] == signal
                and float(p["strike"]) == float(strike)
                and str(p["expiry"]) == str(expiry)
            ):
                return True

        return False

    def _load_json(self, path, default):
        if not path.exists():
            return default

        with open(path, "r") as f:
            return json.load(f)

    def _save_json(self, path, data):
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def save(self):
        self._save_json(self.orders_file, self.orders)
        self._save_json(self.positions_file, self.positions)
        self._save_json(self.cash_file, {"cash": self.cash})

    def submit_order(
        self,
        symbol,
        signal,
        strategy,
        strike,
        expiry,
        quantity,
        price,
        implied_volatility=0.25,
    ):
        quantity = int(quantity)
        price = float(price)

        if quantity <= 0:
            return None

        if self.has_open_position(symbol, signal, strike, expiry):
            return None

        cost = quantity * price * 100.0

        if cost > self.cash:
            return None

        order = PaperOrder.create(
            symbol=symbol,
            signal=signal,
            strategy=strategy,
            strike=strike,
            expiry=expiry,
            quantity=quantity,
            price=price,
            implied_volatility=implied_volatility,
        )

        position = PaperPosition(
            order_id=order.id,
            symbol=symbol,
            signal=signal,
            strategy=strategy,
            strike=float(strike),
            expiry=str(expiry),
            quantity=quantity,
            entry_price=price,
            current_price=price,
            opened_at=order.created_at,
            implied_volatility=float(implied_volatility),
        )

        self.cash -= cost

        self.orders.append(order.to_dict())
        self.positions.append(position.to_dict())

        self.save()

        return order

    def open_positions(self):
        return [
            p for p in self.positions
            if p.get("status") == "OPEN"
        ]

    def closed_positions(self):
        return [
            p for p in self.positions
            if p.get("status") == "CLOSED"
        ]

    def mark_position(self, order_id, current_price):
        for p in self.positions:
            if p["order_id"] == order_id and p["status"] == "OPEN":
                pos = PaperPosition(**p)
                pos.mark(current_price)
                p.update(pos.to_dict())
                self.save()
                return pos

        return None

    def close_position(self, order_id, exit_price, reason):
        for p in self.positions:
            if p["order_id"] == order_id and p["status"] == "OPEN":
                pos = PaperPosition(**p)
                realized = pos.close(exit_price, reason)

                self.cash += exit_price * pos.quantity * 100.0

                p.update(pos.to_dict())
                self.save()

                return pos

        return None

    def summary(self):
        open_value = sum(
            float(p["current_price"]) * int(p["quantity"]) * 100.0
            for p in self.open_positions()
        )

        unrealized_pnl = sum(
            float(p.get("unrealized_pnl", 0.0))
            for p in self.open_positions()
        )

        realized_pnl = sum(
            float(p.get("realized_pnl", 0.0))
            for p in self.closed_positions()
        )

        return {
            "cash": self.cash,
            "open_positions": len(self.open_positions()),
            "closed_positions": len(self.closed_positions()),
            "open_value": open_value,
            "net_liquidation": self.cash + open_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
        }
