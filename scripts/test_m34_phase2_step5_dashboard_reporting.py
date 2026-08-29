from datetime import date
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from pathlib import Path

from trading_ai.research_workstation.analysis import (
    CandidateAnalysisEngine,
    OptionChainExplorerEngine,
)
from trading_ai.research_workstation.analytics import (
    PayoffAnalysisEngine,
    StrategyLegProfile,
)
from trading_ai.research_workstation.dashboard import (
    ResearchDashboardService,
    research_dashboard_payload,
    write_research_dashboard_html,
    write_research_dashboard_json,
)
from trading_ai.research_workstation.explainability import (
    InstitutionalExplainabilityEngine,
)
from trading_ai.research_workstation.scanner.market_scanner_profile import (
    MarketCandidateProfile,
)


def main() -> None:
    market = MarketCandidateProfile(
        symbol="AAA",
        price=100.0,
        average_volume=2_000_000,
        option_volume=5_000,
        open_interest=20_000,
        spread_pct=0.05,
        iv_rank=70.0,
        iv_percentile=75.0,
        atr_pct=2.0,
        trend_score=82.0,
        momentum_score=78.0,
        liquidity_score=90.0,
        volatility_score=80.0,
        regime_score=85.0,
        decision_confidence=92.0,
        expected_return=0.22,
        risk_score=18.0,
        reward_risk_ratio=2.0,
        signal="CALL",
        regime="TREND_UP",
        metadata={
            "institutional_decision": {
                "available": True,
                "allowed": True,
                "selected": True,
                "action": "ENTER",
                "readiness": "READY",
                "strategy": "BULL_PUT_SPREAD",
                "probability_of_profit": 0.78,
                "calibrated_probability": 0.81,
                "institutional_score": 88.0,
                "tail_risk_grade": "A",
                "recommended_position_size_pct": 2.5,
            }
        },
    )
    candidate = CandidateAnalysisEngine().analyze(
        market,
        composite_score=91.5,
    )

    contracts = [
        SimpleNamespace(
            expiry=date(2026, 8, 21),
            strike=100.0,
            option_type="PUT",
            bid=2.9,
            ask=3.1,
            last=3.0,
            volume=1800,
            open_interest=8500,
            implied_volatility=0.29,
            delta=-0.48,
            gamma=0.04,
            theta=-0.08,
            vega=0.12,
        ),
        SimpleNamespace(
            expiry=date(2026, 8, 21),
            strike=95.0,
            option_type="PUT",
            bid=1.1,
            ask=1.3,
            last=1.2,
            volume=1200,
            open_interest=6000,
            implied_volatility=0.31,
            delta=-0.20,
            gamma=0.03,
            theta=-0.05,
            vega=0.08,
        ),
    ]
    chain = OptionChainExplorerEngine().analyze(
        symbol="AAA",
        underlying_price=100.0,
        contracts=contracts,
        quote_date=date(2026, 7, 19),
    )

    payoff = PayoffAnalysisEngine().analyze(
        strategy_name="BULL_PUT_SPREAD",
        underlying_price=100.0,
        legs=(
            StrategyLegProfile(
                symbol="AAA",
                option_type="PUT",
                side="SHORT",
                strike=100.0,
                premium=3.0,
                delta=-0.48,
                gamma=0.04,
                theta=-0.08,
                vega=0.12,
            ),
            StrategyLegProfile(
                symbol="AAA",
                option_type="PUT",
                side="LONG",
                strike=95.0,
                premium=1.2,
                delta=-0.20,
                gamma=0.03,
                theta=-0.05,
                vega=0.08,
            ),
        ),
        minimum_price=80.0,
        maximum_price=120.0,
        steps=161,
    )

    explainability = InstitutionalExplainabilityEngine().analyze(
        candidate=candidate,
        payoff=payoff,
    )
    dashboard = ResearchDashboardService().build(
        candidate=candidate,
        option_chain=chain,
        payoff=payoff,
        explainability=explainability,
    )

    assert dashboard.symbol == "AAA"
    assert dashboard.strategy == "BULL_PUT_SPREAD"
    assert dashboard.approval_status == "APPROVED"
    assert len(dashboard.summary_cards) == 4
    assert len(dashboard.sections) == 4
    assert dashboard.metadata["phase_status"] == "COMPLETE"

    payload = research_dashboard_payload(dashboard)
    assert payload["symbol"] == "AAA"
    assert payload["sections"][0]["title"] == "Candidate Analysis"
    assert payload["sections"][1]["title"] == "Option Chain Explorer"
    assert payload["sections"][2]["title"] == "Payoff and Greeks"
    assert payload["sections"][3]["title"] == "Institutional Explainability"

    with TemporaryDirectory() as directory:
        root = Path(directory)
        json_file = write_research_dashboard_json(
            dashboard,
            root / "dashboard.json",
        )
        html_file = write_research_dashboard_html(
            dashboard,
            root / "dashboard.html",
        )
        assert json_file.exists()
        assert html_file.exists()
        html = html_file.read_text(encoding="utf-8")
        assert "Institutional Research Workstation" in html
        assert "Candidate Analysis" in html
        assert "Option Chain Explorer" in html
        assert "Payoff and Greeks" in html
        assert "Institutional Explainability" in html

    print(
        "All Milestone 34 Phase 2 Step 5 dashboard/reporting "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
