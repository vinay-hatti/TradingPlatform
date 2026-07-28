from __future__ import annotations

import hashlib

from trading_ai.broker.ibkr.order_models import IbkrPaperOrderRequest
from trading_ai.order_management.order_profile import (
    CanonicalOrderCommand,
    CanonicalOrderLeg,
)

from .profile import AutomatedPaperOrderCandidate


def _stable(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:24]
    return f"{prefix}-{digest.upper()}"


class AutomatedPaperOrderFactory:
    @staticmethod
    def identifiers(candidate: AutomatedPaperOrderCandidate) -> tuple[str, str, str]:
        basis = (
            candidate.portfolio_id,
            candidate.candidate_id,
            candidate.symbol.upper(),
            candidate.asset_class.upper(),
            candidate.side.upper(),
            candidate.quantity,
            candidate.order_type.upper(),
            candidate.limit_price,
            candidate.expiry,
            candidate.strike,
            candidate.right.upper(),
        )
        return (
            _stable("M51-AUTO", *basis),
            _stable("M51-CLIENT", *basis),
            _stable("M51-IDEM", *basis),
        )

    def canonical_command(
        self, candidate: AutomatedPaperOrderCandidate
    ) -> CanonicalOrderCommand:
        aggregate_id, client_order_id, idempotency_key = self.identifiers(candidate)
        asset_class = candidate.asset_class.upper()
        normalized_asset = "OPTION" if asset_class == "OPTION" else "EQUITY"
        leg = CanonicalOrderLeg(
            leg_id="LEG-1",
            symbol=candidate.symbol.upper(),
            broker_symbol=candidate.local_symbol or None,
            asset_class=normalized_asset,
            side=candidate.side.upper(),
            quantity=float(candidate.quantity),
            position_effect="OPEN",
            metadata={
                "currency": candidate.currency,
                "primary_exchange": candidate.primary_exchange,
                "contract_id": candidate.contract_id,
                "expiry": candidate.expiry,
                "strike": candidate.strike,
                "right": candidate.right.upper(),
                "multiplier": candidate.multiplier or ("100" if normalized_asset == "OPTION" else "1"),
                **candidate.metadata,
            },
        )
        order_type = candidate.order_type.upper().replace("_", " ")
        canonical_order_type = {
            "MKT": "MARKET",
            "LMT": "LIMIT",
            "STP": "STOP",
            "STP LMT": "STOP_LIMIT",
        }.get(order_type, order_type.replace(" ", "_"))
        return CanonicalOrderCommand(
            command_id=_stable("M51-CMD", idempotency_key),
            command_type="CREATE",
            aggregate_id=aggregate_id,
            client_order_id=client_order_id,
            account_id=candidate.portfolio_id,
            idempotency_key=idempotency_key,
            order_type=canonical_order_type,
            time_in_force=candidate.time_in_force.upper(),
            legs=(leg,),
            limit_price=candidate.limit_price,
            stop_price=candidate.stop_price,
            outside_regular_hours=False,
            strategy_name=candidate.strategy_name,
            correlation_id=candidate.candidate_id,
            metadata={
                "milestone": 51,
                "phase": 1,
                "step": 1,
                "candidate_id": candidate.candidate_id,
                "institutional_allowed": candidate.institutional_allowed,
                "risk_gateway_allowed": candidate.risk_gateway_allowed,
                "decision_score": candidate.decision_score,
                "probability": candidate.probability,
                "paper_only": True,
                "live_trading_enabled": False,
            },
        )

    def ibkr_request(
        self,
        candidate: AutomatedPaperOrderCandidate,
        *,
        broker_account_id: str,
    ) -> IbkrPaperOrderRequest:
        aggregate_id, client_order_id, _ = self.identifiers(candidate)
        asset_class = candidate.asset_class.upper()
        security_type = "OPT" if asset_class == "OPTION" else "STK"
        right = candidate.right.upper()
        if right == "CALL":
            right = "C"
        elif right == "PUT":
            right = "P"
        order_type = {
            "MARKET": "MKT",
            "LIMIT": "LMT",
            "STOP": "STP",
            "STOP_LIMIT": "STP LMT",
        }[candidate.order_type.upper().replace(" ", "_")]
        return IbkrPaperOrderRequest(
            aggregate_id=aggregate_id,
            client_order_id=client_order_id,
            portfolio_id=candidate.portfolio_id,
            broker_account_id=broker_account_id,
            symbol=candidate.symbol.upper(),
            security_type=security_type,
            side=candidate.side.upper(),
            quantity=float(candidate.quantity),
            order_type=order_type,
            time_in_force=candidate.time_in_force.upper(),
            limit_price=candidate.limit_price,
            stop_price=candidate.stop_price,
            currency=candidate.currency.upper(),
            exchange="SMART",
            primary_exchange=candidate.primary_exchange,
            contract_id=int(candidate.contract_id),
            local_symbol=candidate.local_symbol,
            expiry=candidate.expiry.replace("-", ""),
            strike=candidate.strike,
            right=right,
            multiplier=candidate.multiplier or ("100" if security_type == "OPT" else ""),
            outside_regular_hours=False,
            transmit=True,
            metadata={
                "milestone": 51,
                "phase": 1,
                "step": 1,
                "candidate_id": candidate.candidate_id,
                "paper_only": True,
                **candidate.metadata,
            },
        )
