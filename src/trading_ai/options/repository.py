from datetime import date

from sqlalchemy import and_

from market.option_models import OptionContractHistory
from trading_ai.options.contract import OptionContract


class OptionChainRepository:

    def __init__(self, session):
        self.session = session

    def save_many(self, contracts):
        rows = []

        for c in contracts:
            rows.append(
                OptionContractHistory(
                    underlying_symbol=c.underlying_symbol,
                    option_symbol=c.option_symbol,
                    quote_date=c.quote_date,
                    expiry=c.expiry,
                    option_type=c.option_type,
                    strike=float(c.strike),
                    bid=float(c.bid),
                    ask=float(c.ask),
                    mid=float(c.mid),
                    last=float(c.last),
                    volume=int(c.volume),
                    open_interest=int(c.open_interest),
                    implied_volatility=float(c.implied_volatility),
                    delta=float(c.delta),
                    gamma=float(c.gamma),
                    theta=float(c.theta),
                    vega=float(c.vega),
                    rho=float(c.rho),
                )
            )

        self.session.add_all(rows)
        self.session.commit()

        return len(rows)

    def find_chain(
        self,
        underlying_symbol,
        quote_date,
        option_type=None,
        expiry=None,
    ):
        query = self.session.query(OptionContractHistory).filter(
            OptionContractHistory.underlying_symbol == underlying_symbol,
            OptionContractHistory.quote_date == quote_date,
        )

        if option_type:
            query = query.filter(
                OptionContractHistory.option_type == option_type.upper()
            )

        if expiry:
            query = query.filter(
                OptionContractHistory.expiry == expiry
            )

        return [
            self._to_domain(row)
            for row in query.order_by(
                OptionContractHistory.expiry,
                OptionContractHistory.strike,
            ).all()
        ]

    def find_nearest_contract(
        self,
        underlying_symbol,
        quote_date,
        option_type,
        target_strike,
        target_dte,
    ):
        rows = self.session.query(OptionContractHistory).filter(
            OptionContractHistory.underlying_symbol == underlying_symbol,
            OptionContractHistory.quote_date == quote_date,
            OptionContractHistory.option_type == option_type.upper(),
        ).all()

        if not rows:
            return None

        def score(row):
            dte = (row.expiry - quote_date).days
            return (
                abs(float(row.strike) - float(target_strike))
                + abs(dte - int(target_dte)) * 2.0
            )

        best = sorted(rows, key=score)[0]

        return self._to_domain(best)

    def find_exact(
        self,
        underlying_symbol,
        quote_date,
        option_type,
        expiry,
        strike,
    ):
        row = self.session.query(OptionContractHistory).filter(
            OptionContractHistory.underlying_symbol == underlying_symbol,
            OptionContractHistory.quote_date == quote_date,
            OptionContractHistory.option_type == option_type.upper(),
            OptionContractHistory.expiry == expiry,
            OptionContractHistory.strike == float(strike),
        ).first()

        return self._to_domain(row) if row else None

    def _to_domain(self, row):
        return OptionContract(
            underlying_symbol=row.underlying_symbol,
            option_symbol=row.option_symbol,
            quote_date=row.quote_date,
            expiry=row.expiry,
            option_type=row.option_type,
            strike=row.strike,
            bid=row.bid,
            ask=row.ask,
            mid=row.mid,
            last=row.last,
            volume=row.volume,
            open_interest=row.open_interest,
            implied_volatility=row.implied_volatility,
            delta=row.delta,
            gamma=row.gamma,
            theta=row.theta,
            vega=row.vega,
            rho=row.rho,
        )
