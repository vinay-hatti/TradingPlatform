from polygon import RESTClient
from trading_ai.config import settings
from trading_ai.domain.option import OptionContract
from trading_ai.volatility.iv_surface import IVSurfaceEngine
from trading_ai.volatility.term_structure import TermStructureBuilder
from trading_ai.volatility.skew import SkewEngine
from trading_ai.volatility.iv_rank import IVRankEngine


class PolygonOptionsProvider:

    def __init__(self):
        self.client = RESTClient(settings.polygon_api_key)

        self.iv_surface = IVSurfaceEngine()
        self.term_structure = TermStructureBuilder()
        self.skew_engine = SkewEngine()
        self.iv_rank_engine = IVRankEngine()

        self.analytics = {}

    def get_chain(self, symbol: str):

        chain = []

        contracts = self.client.list_snapshot_options_chain(symbol)

        for c in contracts:

            try:
                details = c.details
                if details is None:
                    continue

                greeks = c.greeks

                if greeks is None or greeks.delta is None:
                    continue

                iv = float(c.implied_volatility or 0.0)
                delta = float(greeks.delta)
                gamma = float(greeks.gamma or 0.0)
                theta = float(greeks.theta or 0.0)
                vega = float(greeks.vega or 0.0)

                chain.append(
                    OptionContract(
                        underlying=symbol,
                        option_symbol=details.ticker,
                        strike=float(details.strike_price),
                        expiry=str(details.expiration_date),
                        option_type=str(details.contract_type).upper(),
                        bid=0.0,
                        ask=0.0,
                        last=0.0,
                        volume=0,
                        open_interest=int(c.open_interest or 0),
                        implied_volatility=iv,
                        delta=delta,
                        gamma=gamma,
                        theta=theta,
                        vega=vega,
                        rho=0.0,
                    )
                )

            except Exception:
                continue

        # -----------------------------
        # POST-PROCESSING (FIXED)
        # -----------------------------
        ivs = [c.implied_volatility for c in chain if c.implied_volatility > 0]

        if len(ivs) > 0:
            iv_rank_data = self.iv_rank_engine.compute(symbol, ivs)
            iv_rank = iv_rank_data["iv_rank"]
        else:
            iv_rank = 0.5

        surface = self.iv_surface.build_surface(chain)
        term = self.term_structure.build(chain)
        skew = self.skew_engine.compute_skew(chain)

        self.analytics = {
            "iv_rank": iv_rank,
            "surface": surface,
            "term_structure": term,
            "skew": skew,
        }

        return chain

    def get_analytics(self, symbol: str):

        # Delegate to options provider if available
        if hasattr(self, "options_provider"):
            return self.options_provider.get_analytics(symbol)

        return {
            "iv_rank": 0.5,
            "skew": {"skew": 0.0},
        }
