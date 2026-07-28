from trading_ai.paper_trading.automated_order_handoff import (
    InstitutionalDecisionBatchHandoffService,
)


class FakeHandoff:
    def execute(self, candidate, *, mode, confirmation):
        class Result:
            status = "DRY_RUN_READY"
            def to_dict(self):
                return {
                    "status": self.status,
                    "candidate_id": candidate.candidate_id,
                    "mode": mode,
                }
        return Result()


def test_batch_only_hands_off_accepted_decisions():
    service = InstitutionalDecisionBatchHandoffService.__new__(
        InstitutionalDecisionBatchHandoffService
    )
    from trading_ai.paper_trading.automated_order_handoff import (
        InstitutionalDecisionHandoffAdapter,
    )
    service.adapter = InstitutionalDecisionHandoffAdapter()
    service.handoff = FakeHandoff()

    result = service.execute(
        {
            "run": {
                "scan_id": "scan-1",
                "decisions_by_symbol": {
                    "AAPL": {
                        "available": True,
                        "allowed": True,
                        "selected": True,
                        "action": "BUY",
                        "readiness": "READY",
                        "strategy": "TREND",
                        "decision_confidence": 80,
                        "calibrated_probability": 0.65,
                    }
                },
            },
            "candidates": [
                {
                    "symbol": "AAPL",
                    "source": {
                        "price": 200,
                        "metadata": {
                            "asset_class": "EQUITY",
                            "risk_gateway_allowed": True,
                        },
                    },
                }
            ],
        },
        mode="DRY_RUN",
    )
    assert result.accepted_conversions == 1
    assert result.handoff_succeeded == 1
    assert result.status == "INSTITUTIONAL_HANDOFF_BATCH_COMPLETED"
