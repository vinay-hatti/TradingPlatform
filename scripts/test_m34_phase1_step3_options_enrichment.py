from __future__ import annotations

from datetime import date

from trading_ai.research_workstation.scanner import (
    MarketCandidateProfile,
    OptionContractSnapshot,
    OptionsEnrichmentEngine,
    OptionsEnrichmentService,
)


class FakeOptionsDataAdapter:
    def __init__(self, data):
        self.data = data

    def load_contracts(self, *, symbols, start=None, end=None):
        return {symbol: tuple(self.data.get(symbol, ())) for symbol in symbols}


def contract(
    symbol: str,
    quote_date: date,
    iv: float,
    volume: int,
    open_interest: int,
    bid: float,
    ask: float,
) -> OptionContractSnapshot:
    return OptionContractSnapshot(
        underlying_symbol=symbol,
        expiry=date(2026, 9, 18),
        quote_date=quote_date,
        strike=100.0,
        option_type="call",
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2.0,
        volume=volume,
        open_interest=open_interest,
        implied_volatility=iv,
        delta=0.5,
        gamma=0.1,
        theta=-0.05,
        vega=0.2,
    )


def candidate(symbol: str) -> MarketCandidateProfile:
    return MarketCandidateProfile(
        symbol=symbol,
        price=100.0,
        average_volume=2_000_000,
        option_volume=0,
        open_interest=0,
        spread_pct=1.0,
        iv_rank=0.0,
        iv_percentile=0.0,
        atr_pct=2.0,
        trend_score=75.0,
        momentum_score=70.0,
        liquidity_score=80.0,
        volatility_score=60.0,
        regime_score=80.0,
        decision_confidence=50.0,
        expected_return=0.0,
        risk_score=50.0,
        reward_risk_ratio=0.0,
        signal="CALL",
        regime="TREND_UP",
    )


def main() -> None:
    d1 = date(2026, 7, 1)
    d2 = date(2026, 7, 2)
    d3 = date(2026, 7, 3)

    data = {
        "AAA": (
            contract("AAA", d1, 0.20, 10, 100, 1.00, 1.10),
            contract("AAA", d2, 0.30, 20, 200, 1.00, 1.08),
            contract("AAA", d3, 0.40, 30, 300, 1.00, 1.05),
            contract("AAA", d3, 0.42, 40, 400, 2.00, 2.08),
        ),
    }

    engine = OptionsEnrichmentEngine(
        minimum_contract_volume=1,
        minimum_contract_open_interest=1,
        maximum_contract_spread_pct=0.20,
    )

    snapshot = engine.build_snapshot("AAA", data["AAA"])
    assert snapshot is not None
    assert snapshot.quote_date == d3
    assert snapshot.option_volume == 70
    assert snapshot.open_interest == 700
    assert snapshot.contract_count == 2
    assert snapshot.liquid_contract_count == 2
    assert snapshot.median_spread_pct < 0.10
    assert snapshot.iv_rank == 100.0
    assert snapshot.iv_percentile == 100.0

    service = OptionsEnrichmentService(
        adapter=FakeOptionsDataAdapter(data),
        engine=engine,
    )

    enriched = service.enrich((candidate("AAA"), candidate("BBB")))
    by_symbol = {item.symbol: item for item in enriched}

    assert by_symbol["AAA"].option_volume == 70
    assert by_symbol["AAA"].open_interest == 700
    assert by_symbol["AAA"].iv_rank == 100.0
    assert by_symbol["AAA"].iv_percentile == 100.0
    assert by_symbol["AAA"].spread_pct < 0.10
    assert by_symbol["AAA"].metadata["options_contract_count"] == 2

    assert by_symbol["BBB"].option_volume == 0
    assert by_symbol["BBB"].open_interest == 0
    assert by_symbol["BBB"].spread_pct == 1.0

    print("All Milestone 34 Phase 1 Step 3 options enrichment assertions passed.")


if __name__ == "__main__":
    main()
