from trading_ai.paper_trading.automated_order_handoff import (
    AutomatedPaperTradingPhaseService,
)


class FakeHandoff:
    def execute(self, candidate, *, mode, confirmation):
        class Result:
            status = "DRY_RUN_READY"
            def to_dict(self):
                return {"status": self.status, "candidate_id": candidate.candidate_id}
        return Result()


def test_phase_orchestration_runs_conversion_exposure_and_handoff():
    service = AutomatedPaperTradingPhaseService.__new__(
        AutomatedPaperTradingPhaseService
    )
    from trading_ai.paper_trading.automated_order_handoff import (
        AutomatedPortfolioExposureEngine,
        InstitutionalDecisionHandoffAdapter,
    )
    service.adapter = InstitutionalDecisionHandoffAdapter()
    service.exposure_engine = AutomatedPortfolioExposureEngine()
    service.exposure_provider = lambda _: {
        "net_liquidation_value": 100000,
        "cash_balance": 90000,
        "capital_committed": 10000,
        "open_position_count": 2,
        "by_symbol": [],
        "by_sector": [],
    }
    service.handoff = FakeHandoff()

    result = service.execute({
        "run": {
            "scan_id": "scan",
            "decisions_by_symbol": {
                "AAPL": {
                    "available": True,
                    "allowed": True,
                    "selected": True,
                    "action": "BUY",
                    "readiness": "READY",
                    "strategy": "TREND",
                    "decision_confidence": 80,
                    "calibrated_probability": 0.7,
                }
            },
        },
        "candidates": [{
            "symbol": "AAPL",
            "source": {
                "price": 100,
                "metadata": {
                    "asset_class": "EQUITY",
                    "risk_gateway_allowed": True,
                },
            },
        }],
    })
    assert result.status == "PHASE1_AUTOMATED_PAPER_HANDOFF_COMPLETED"
    assert result.handoff_succeeded == 1
    assert result.exposure_accepted == 1
