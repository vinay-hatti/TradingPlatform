from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable


class OpportunityState(str, Enum):
    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    STRATEGIES_GENERATED = "STRATEGIES_GENERATED"
    CONTRACTS_OPTIMIZED = "CONTRACTS_OPTIMIZED"
    READY_FOR_EXECUTION = "READY_FOR_EXECUTION"
    EXECUTED = "EXECUTED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ATTRIBUTED = "ATTRIBUTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ThesisDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class StrategyDisposition(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    CONDITIONAL = "CONDITIONAL"
    REJECTED = "REJECTED"
    SELECTED = "SELECTED"


class ContractSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class OpportunityLineage:
    stock_publication_name: str
    stock_scanner_run_id: str
    stock_candidate_id: str
    stock_state_hash: str
    market_publication_name: str | None = None
    market_run_id: str | None = None
    option_snapshot_id: str | None = None
    source_option_snapshot_id: str | None = None
    contract_option_snapshot_id: str | None = None
    option_snapshot_timestamp: str | None = None
    source_provider: str = "POLYGON_PERSISTED"

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "OpportunityLineage":
        """Deserialize persisted lineage without breaking on versioned extensions.

        M68.2.1.3 split the raw source option snapshot from the exact contract
        snapshot.  Older opportunity rows contain only ``option_snapshot_id``;
        newer rows contain both explicit fields.  This boundary accepts both
        contracts, ignores unrelated future keys, and keeps the legacy alias
        pinned to the exact contract snapshot when one exists.
        """

        raw = dict(payload or {})
        allowed = {item.name for item in fields(cls)}
        values = {key: value for key, value in raw.items() if key in allowed}
        legacy = values.get("option_snapshot_id")
        source = values.get("source_option_snapshot_id") or legacy
        contract = values.get("contract_option_snapshot_id") or legacy
        values["source_option_snapshot_id"] = source
        values["contract_option_snapshot_id"] = contract
        values["option_snapshot_id"] = contract or legacy or source
        return cls(**values)


@dataclass(frozen=True)
class OpportunityThesis:
    thesis_id: str
    opportunity_id: str
    direction: ThesisDirection
    setup_category: str
    primary_timeframe: str
    market_regime: str | None
    sector_context: str | None
    trend_state: str
    structure_state: str
    participation_state: str | None
    dealer_context: str | None
    forecast_context: str | None
    entry_zone_low: float
    entry_zone_high: float
    invalidation_level: float
    targets: tuple[float, ...]
    expected_holding_days_min: int | None = None
    expected_holding_days_max: int | None = None
    evidence: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class InstitutionalOpportunity:
    opportunity_id: str
    symbol: str
    asset_class: str
    state: OpportunityState
    direction: ThesisDirection
    category: str
    overall_score: float
    confidence: float
    conviction: str
    lineage: OpportunityLineage
    thesis_id: str
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    inflection_intelligence: dict[str, Any] = field(default_factory=dict)
    intelligence_extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any] | None,
    ) -> "InstitutionalOpportunity":
        """Deserialize a versioned opportunity payload without losing evidence.

        Inflection and later intelligence milestones enrich persisted opportunity
        payloads additively.  Rehydrating those rows with ``cls(**payload)`` makes
        an additive evidence field a runtime-breaking schema change.  This
        boundary converts the governed enum/lineage fields, accepts the current
        Inflection contract explicitly, and retains unknown future fields under
        ``intelligence_extensions`` instead of discarding them.
        """

        raw = dict(payload or {})
        allowed = {item.name for item in fields(cls)}
        extensions = dict(raw.get("intelligence_extensions") or {})
        extensions.update({
            key: value
            for key, value in raw.items()
            if key not in allowed
        })
        values = {
            key: value
            for key, value in raw.items()
            if key in allowed
        }
        values["state"] = OpportunityState(values["state"])
        values["direction"] = ThesisDirection(values["direction"])
        values["lineage"] = OpportunityLineage.from_payload(
            values.get("lineage")
        )
        values["metadata"] = dict(values.get("metadata") or {})
        values["inflection_intelligence"] = dict(
            values.get("inflection_intelligence") or {}
        )
        values["intelligence_extensions"] = extensions
        return cls(**values)


@dataclass(frozen=True)
class ProbabilityDecomposition:
    underlying_probability: float
    option_payoff_probability: float | None = None
    regime_adjustment: float = 0.0
    structure_adjustment: float = 0.0
    dealer_adjustment: float = 0.0
    liquidity_adjustment: float = 0.0
    calibrated_probability: float | None = None
    model_family: str | None = None
    model_version: str | None = None


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_candidate_id: str
    opportunity_id: str
    strategy: str
    disposition: StrategyDisposition
    eligibility_score: float
    strategy_score: float | None = None
    complexity: str = "MEDIUM"
    capital_required: float | None = None
    maximum_loss: float | None = None
    expected_value: float | None = None
    expected_return_on_risk: float | None = None
    structural_reward_risk: float | None = None
    probability: ProbabilityDecomposition | None = None
    accepted_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    rank: int | None = None
    selected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContractLegRecommendation:
    leg_id: str
    side: ContractSide
    option_type: str
    option_symbol: str
    expiry: str
    strike: float
    quantity_ratio: int = 1
    contract_id: int | None = None
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    implied_volatility: float | None = None
    implied_volatility_raw: float | None = None
    implied_volatility_status: str | None = None
    implied_volatility_source: str | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    multiplier: str = "100"
    dte: int | None = None
    quote_date: str | None = None
    quote_timestamp: str | None = None
    source_underlying_price: float | None = None


@dataclass(frozen=True)
class ContractRecommendation:
    contract_recommendation_id: str
    strategy_candidate_id: str
    opportunity_id: str
    option_snapshot_id: str
    legs: tuple[ContractLegRecommendation, ...]
    strategy: str | None = None
    net_debit_credit: float | None = None
    estimated_slippage: float | None = None
    liquidity_score: float | None = None
    executable: bool = False
    validation_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    optimization_scores: dict[str, float] = field(default_factory=dict)
    option_valuation_intelligence: dict[str, Any] = field(default_factory=dict)
    intelligence_extensions: dict[str, Any] = field(default_factory=dict)
    market_data_as_of: str | None = None
    underlying_price: float | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class StrategyComparison:
    comparison_id: str
    opportunity_id: str
    ranked_strategy_candidate_ids: tuple[str, ...]
    selected_strategy_candidate_id: str | None
    comparison_policy_version: str
    rationale: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class ExecutionRecommendation:
    execution_recommendation_id: str
    opportunity_id: str
    strategy_candidate_id: str
    contract_recommendation_id: str
    underlying_entry_zone_low: float
    underlying_entry_zone_high: float
    underlying_stop: float
    underlying_targets: tuple[float, ...]
    trailing_policy: str
    emergency_option_stop_pct: float | None = None
    theta_exit_days_to_expiry: int | None = None
    volatility_exit_rule: str | None = None
    invalidation_reasons: tuple[str, ...] = ()
    ready_for_trade_builder: bool = False
    trade_plan_certification: dict[str, Any] | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class OpportunityOutcomeAttribution:
    attribution_id: str
    opportunity_id: str
    strategy_candidate_id: str | None
    contract_recommendation_id: str | None
    predicted_probability: float | None
    realized_return_pct: float | None
    outcome: str | None
    exit_reason: str | None
    mfe_pct: float | None = None
    mae_pct: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_primitive(item) for item in value]
    return value



def deserialize_contract_recommendation(payload: dict[str, Any]) -> ContractRecommendation:
    """Rehydrate a persisted contract payload without allowing future enrichments to break M62.

    Known recommendation fields are passed directly. Unknown top-level fields are preserved in
    ``intelligence_extensions`` so additive intelligence milestones remain backward compatible.
    """
    raw = dict(payload or {})
    legs = tuple(
        ContractLegRecommendation(**(dict(leg) | {"side": ContractSide(leg["side"])}))
        for leg in raw.pop("legs", ()) or ()
    )
    raw["validation_reasons"] = tuple(raw.get("validation_reasons") or ())
    raw["rejection_reasons"] = tuple(raw.get("rejection_reasons") or ())
    known = set(ContractRecommendation.__dataclass_fields__)
    extensions = dict(raw.get("intelligence_extensions") or {})
    for key in tuple(raw):
        if key not in known:
            extensions[key] = raw.pop(key)
    raw["intelligence_extensions"] = extensions
    raw["option_valuation_intelligence"] = dict(raw.get("option_valuation_intelligence") or {})
    return ContractRecommendation(**(raw | {"legs": legs}))

def serialize_domain(value: Any) -> dict[str, Any]:
    result = _primitive(value)
    if not isinstance(result, dict):
        raise TypeError("Milestone 62 domain serialization requires a dataclass or mapping")
    return result


def deterministic_hash(*values: Any) -> str:
    payload = [_primitive(value) for value in values]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def ensure_unique_contract_symbols(legs: Iterable[ContractLegRecommendation]) -> None:
    symbols = [leg.option_symbol.strip() for leg in legs]
    if any(not symbol for symbol in symbols):
        raise ValueError("Every option leg must carry an exact Polygon option_symbol")
    if len(symbols) != len(set(symbols)):
        raise ValueError("Multi-leg recommendations must use distinct exact option contracts")
