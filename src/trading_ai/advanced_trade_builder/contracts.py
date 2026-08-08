from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class TradePlanState(str, Enum):
    DRAFT = 'DRAFT'
    VALIDATED = 'VALIDATED'
    APPROVED = 'APPROVED'
    PAPER_READY = 'PAPER_READY'
    CANCELLED = 'CANCELLED'


class LegSide(str, Enum):
    BUY = 'BUY'
    SELL = 'SELL'


class OptionRight(str, Enum):
    CALL = 'CALL'
    PUT = 'PUT'


@dataclass(frozen=True)
class TradeLeg:
    side: LegSide
    quantity: int
    option_right: OptionRight
    strike: float
    expiry: str
    limit_price: float
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    option_symbol: str | None = None


@dataclass(frozen=True)
class BuildTradePlanRequest:
    opportunity_id: str
    expected_opportunity_version: int
    account_id: str
    strategy: str
    capital: float
    risk_budget_pct: float
    legs: tuple[TradeLeg, ...]
    actor: str
    entry_debit: float | None = None
    max_profit: float | None = None
    notes: str = ''


@dataclass(frozen=True)
class TradePlan:
    trade_plan_id: str
    opportunity_id: str
    opportunity_version: int
    intelligence_id: str | None
    account_id: str
    symbol: str
    direction: str
    strategy: str
    state: TradePlanState
    version: int
    capital: float
    risk_budget_pct: float
    risk_budget_amount: float
    estimated_debit: float
    estimated_credit: float
    max_loss: float
    max_profit: float | None
    reward_risk_ratio: float | None
    net_greeks: dict[str, float]
    validation: dict[str, Any]
    legs: tuple[TradeLeg, ...]
    created_by: str
    created_at: str
    updated_at: str
    notes: str = ''
    execution_intent: dict[str, Any] = field(default_factory=dict)

    _TRANSITIONS = {
        TradePlanState.DRAFT: (TradePlanState.VALIDATED, TradePlanState.CANCELLED),
        TradePlanState.VALIDATED: (TradePlanState.APPROVED, TradePlanState.CANCELLED),
        TradePlanState.APPROVED: (TradePlanState.PAPER_READY, TradePlanState.CANCELLED),
        TradePlanState.PAPER_READY: (TradePlanState.CANCELLED,),
        TradePlanState.CANCELLED: (),
    }

    _LABELS = {
        TradePlanState.VALIDATED: 'Validate',
        TradePlanState.APPROVED: 'Approve',
        TradePlanState.PAPER_READY: 'Mark Paper Ready',
        TradePlanState.CANCELLED: 'Cancel',
    }

    def action_items(self) -> list[dict[str, Any]]:
        validation = dict(self.validation or {})
        valid = bool(validation.get('valid', False))
        items: list[dict[str, Any]] = []

        for target in self._TRANSITIONS.get(self.state, ()):
            enabled = True
            reason = ''
            if target in {
                TradePlanState.VALIDATED,
                TradePlanState.APPROVED,
                TradePlanState.PAPER_READY,
            } and not valid:
                enabled = False
                failed = [
                    str(name)
                    for name, passed in validation.items()
                    if name != 'valid' and passed is False
                ]
                reason = (
                    'Trade plan validation failed'
                    + (f": {', '.join(failed)}" if failed else '')
                )

            items.append({
                'id': f'transition:{target.value}',
                'action': 'TRANSITION',
                'label': self._LABELS[target],
                'target_state': target.value,
                'new_state': target.value,
                'enabled': enabled,
                'disabled': not enabled,
                'reason': reason,
                'method': 'POST',
                'endpoint': f'/api/v1/trade-builder/plans/{self.trade_plan_id}/transitions',
                'expected_version': self.version,
                'requires_reason': True,
            })

        if self.state == TradePlanState.PAPER_READY:
            items.insert(0, {
                'id': 'create_execution_intent',
                'action': 'CREATE_EXECUTION_INTENT',
                'label': 'Create Execution Intent',
                'target_state': None,
                'new_state': None,
                'enabled': valid,
                'disabled': not valid,
                'reason': '' if valid else 'Trade plan validation failed',
                'method': 'POST',
                'endpoint': (
                    '/api/v1/execution-workspace/intents/from-trade-plan/'
                    f'{self.trade_plan_id}'
                ),
                'expected_version': self.version,
                'requires_reason': False,
            })

        return items

    def to_dict(self):
        payload = asdict(self)
        payload['state'] = self.state.value
        for leg in payload.get('legs', []):
            side = leg.get('side')
            right = leg.get('option_right')
            leg['side'] = side.value if isinstance(side, Enum) else side
            leg['option_right'] = right.value if isinstance(right, Enum) else right

        actions = self.action_items()
        # Multiple aliases preserve compatibility with Trade Builder clients
        # released across milestones.
        payload['actions'] = actions
        payload['available_actions'] = actions
        payload['allowed_actions'] = actions
        payload['allowed_transitions'] = [
            item['target_state']
            for item in actions
            if item['action'] == 'TRANSITION' and item['enabled']
        ]
        payload['actionable'] = any(item['enabled'] for item in actions)
        return payload
