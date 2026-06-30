from trading_ai.options.domain import OptionContract
import numpy as np


class SimulatedOptionsProvider:

    def get_chain(self, symbol: str):

        contracts = []

        for strike in [90, 95, 100, 105, 110]:

            contracts.append(
                OptionContract(
                    symbol=symbol,
                    strike=float(strike),
                    expiry="2026-12-31",
                    delta=float(np.random.uniform(0.2, 0.8)),
                    volume=float(np.random.randint(100, 2000)),
                    implied_volatility=float(np.random.uniform(0.15, 0.4)),
                    expected_move_1d=float(np.random.uniform(2, 8)),
                )
            )

        return contracts
