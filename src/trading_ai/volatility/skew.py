class SkewEngine:

    def compute_skew(self, option_chain):

        calls = []
        puts = []

        for opt in option_chain:

            if opt.implied_volatility <= 0:
                continue

            if opt.delta > 0:
                calls.append(opt.implied_volatility)

            else:
                puts.append(opt.implied_volatility)

        return {
            "call_iv": sum(calls) / len(calls) if calls else 0,
            "put_iv": sum(puts) / len(puts) if puts else 0,
            "skew": (
                (sum(puts) / len(puts)) - (sum(calls) / len(calls))
                if calls and puts else 0
            )
        }
