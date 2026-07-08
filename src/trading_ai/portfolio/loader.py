import pandas as pd

from trading_ai.portfolio.models import PortfolioPosition


class PortfolioLoader:

    def load(self, filename):

        df = pd.read_csv(filename)

        positions = []

        for _, row in df.iterrows():

            positions.append(

                PortfolioPosition(

                    symbol=row.symbol,

                    signal=row.signal,

                    strategy=row.strategy,

                    sector=row.sector,

                    contracts=row.contracts,

                    avg_price=row.avg_price,

                    current_price=row.current_price,

                    market_value=row.market_value,

                    delta=row.delta,

                    gamma=row.gamma,

                    theta=row.theta,

                    vega=row.vega,

                    rho=row.rho,

                    entry_date=row.entry_date,

                )

            )

        return positions
