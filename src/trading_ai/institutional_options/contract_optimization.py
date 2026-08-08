from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from math import isfinite
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from trading_ai.market.option_models import OptionContractHistory
from trading_ai.market.models import PriceHistory

from .domain import (
    ContractLegRecommendation,
    ContractRecommendation,
    ContractSide,
    OpportunityState,
    StrategyCandidate,
    StrategyDisposition,
)
from .models import InstitutionalOpportunityModel, StrategyCandidateModel
from .repository import InstitutionalOpportunityRepository


@dataclass(frozen=True)
class ContractOptimizationPolicy:
    target_dte: int = 45
    near_dte: int = 30
    far_dte: int = 75
    minimum_dte: int = 14
    maximum_dte: int = 120
    minimum_open_interest: int = 1
    minimum_volume: int = 0
    maximum_spread_pct: float = 0.35
    maximum_candidates_per_strategy: int = 1
    policy_version: str = "M62-PH4-1.0"


@dataclass(frozen=True)
class ContractOptimizationResult:
    requested: int
    optimized: int
    failed: int
    executable_recommendations: int
    non_executable_recommendations: int
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionContractRecord:
    option_symbol: str
    quote_date: date
    expiry: date
    option_type: str
    strike: float
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float

    @property
    def midpoint(self) -> float:
        if self.ask > 0 and self.bid >= 0:
            return (self.bid + self.ask) / 2.0
        return max(self.last, 0.0)

    @property
    def spread_pct(self) -> float:
        mid = self.midpoint
        return (self.ask - self.bid) / mid if mid > 0 and self.ask >= self.bid else 999.0

    @property
    def dte(self) -> int:
        return max(0, (self.expiry - self.quote_date).days)


class PolygonPersistedOptionRepository:
    def __init__(self, session: Session, policy: ContractOptimizationPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or ContractOptimizationPolicy()

    @staticmethod
    def symbol_aliases(symbol: str) -> tuple[str, ...]:
        normalized = str(symbol or "").strip().upper()
        aliases = [normalized]
        if "-" in normalized:
            aliases.extend((normalized.replace("-", "."), normalized.replace("-", "")))
        if "." in normalized:
            aliases.extend((normalized.replace(".", "-"), normalized.replace(".", "")))
        return tuple(dict.fromkeys(alias for alias in aliases if alias))

    @staticmethod
    def _compact_symbol(symbol: str) -> str:
        return "".join(character for character in str(symbol or "").upper() if character.isalnum())

    def _persisted_aliases(self, column, symbol: str) -> tuple[str, ...]:
        """Resolve unusual vendor separators without changing canonical aliases.

        The public alias contract remains stable, while a small distinct-symbol
        lookup can discover persisted forms such as ``BRK/B`` or ``BRK B``.
        """
        aliases = list(self.symbol_aliases(symbol))
        compact = self._compact_symbol(symbol)
        if not compact:
            return tuple(aliases)
        for (value,) in self.session.query(column).distinct().all():
            text = str(value or "").strip().upper()
            if text and self._compact_symbol(text) == compact and text not in aliases:
                aliases.append(text)
        return tuple(aliases)

    def latest_quote_date(self, symbol: str) -> date:
        aliases = self._persisted_aliases(OptionContractHistory.underlying_symbol, symbol)
        value = self.session.query(func.max(OptionContractHistory.quote_date)).filter(
            func.upper(OptionContractHistory.underlying_symbol).in_(aliases)
        ).scalar()
        if value is None:
            raise LookupError(f"No persisted Polygon option data found for {symbol}")
        return value

    def spot(self, symbol: str, quote_date: date) -> float:
        aliases = self._persisted_aliases(PriceHistory.symbol, symbol)
        row = self.session.query(PriceHistory).filter(
            func.upper(PriceHistory.symbol).in_(aliases),
            PriceHistory.date <= quote_date,
        ).order_by(PriceHistory.date.desc()).first()
        if row is None:
            raise LookupError(f"No underlying price found for {symbol} on or before {quote_date}")
        return float(row.close)

    def contracts(self, symbol: str) -> tuple[date, float, list[OptionContractRecord]]:
        quote_date = self.latest_quote_date(symbol)
        spot = self.spot(symbol, quote_date)
        aliases = self._persisted_aliases(OptionContractHistory.underlying_symbol, symbol)
        rows = self.session.query(OptionContractHistory).filter(
            func.upper(OptionContractHistory.underlying_symbol).in_(aliases),
            OptionContractHistory.quote_date == quote_date,
        ).all()
        result: list[OptionContractRecord] = []
        for row in rows:
            option_type = str(row.option_type or "").upper()
            option_type = "CALL" if option_type in {"C", "CALLS"} else "PUT" if option_type in {"P", "PUTS"} else option_type
            if option_type not in {"CALL", "PUT"}:
                continue
            values = [row.strike, row.bid, row.ask, row.last, row.implied_volatility, row.delta, row.gamma, row.theta, row.vega]
            if any(value is not None and not isfinite(float(value)) for value in values):
                continue
            contract = OptionContractRecord(
                option_symbol=str(row.option_symbol or "").strip(),
                quote_date=quote_date,
                expiry=row.expiry,
                option_type=option_type,
                strike=float(row.strike),
                bid=max(0.0, float(row.bid or 0.0)),
                ask=max(0.0, float(row.ask or 0.0)),
                last=max(0.0, float(row.last or 0.0)),
                volume=max(0, int(row.volume or 0)),
                open_interest=max(0, int(row.open_interest or 0)),
                implied_volatility=max(0.0, float(row.implied_volatility or 0.0)),
                delta=float(row.delta or 0.0), gamma=float(row.gamma or 0.0), theta=float(row.theta or 0.0), vega=float(row.vega or 0.0),
            )
            if not contract.option_symbol:
                continue
            if not (self.policy.minimum_dte <= contract.dte <= self.policy.maximum_dte):
                continue
            if contract.open_interest < self.policy.minimum_open_interest or contract.volume < self.policy.minimum_volume:
                continue
            if contract.ask <= 0 or contract.spread_pct > self.policy.maximum_spread_pct:
                continue
            result.append(contract)
        return quote_date, spot, result


class ExactPolygonContractOptimizer:
    def __init__(self, policy: ContractOptimizationPolicy | None = None) -> None:
        self.policy = policy or ContractOptimizationPolicy()

    @staticmethod
    def _nearest(items: Iterable[OptionContractRecord], *, target_delta: float | None = None, target_strike: float | None = None, target_dte: int | None = None) -> OptionContractRecord:
        rows = list(items)
        if not rows:
            raise LookupError("No executable option contracts satisfy the requested leg")
        def score(item: OptionContractRecord) -> tuple[float, float, float, float]:
            delta_error = abs(abs(item.delta) - abs(target_delta)) if target_delta is not None else 0.0
            strike_error = abs(item.strike - target_strike) if target_strike is not None else 0.0
            dte_error = abs(item.dte - target_dte) if target_dte is not None else 0.0
            liquidity_penalty = item.spread_pct - min(item.open_interest / 100000.0, 0.1)
            return (dte_error, delta_error, strike_error, liquidity_penalty)
        return min(rows, key=score)

    def _leg(self, row: OptionContractRecord, side: ContractSide, ratio: int = 1) -> ContractLegRecommendation:
        return ContractLegRecommendation(
            leg_id=f"m62-leg-{uuid4().hex}", side=side, option_type=row.option_type,
            option_symbol=row.option_symbol, expiry=row.expiry.isoformat(), strike=row.strike,
            quantity_ratio=ratio, bid=row.bid, ask=row.ask, last=row.last, volume=row.volume,
            open_interest=row.open_interest, implied_volatility=row.implied_volatility,
            delta=row.delta, gamma=row.gamma, theta=row.theta, vega=row.vega,
        )

    @staticmethod
    def _scorecard(legs: list[ContractLegRecommendation], rows: list[OptionContractRecord]) -> dict[str, float]:
        if not legs:
            return {
                "liquidity": 0.0, "spread_quality": 0.0, "greeks_quality": 0.0,
                "iv_quality": 0.0, "execution_quality": 0.0, "overall_contract_score": 0.0,
            }
        row_map = {row.option_symbol: row for row in rows}
        selected = [row_map[leg.option_symbol] for leg in legs]
        spread_quality = sum(max(0.0, 100.0 * (1.0 - min(row.spread_pct, 1.0))) for row in selected) / len(selected)
        depth_quality = sum(min(100.0, row.open_interest / 10.0 + row.volume / 5.0) for row in selected) / len(selected)
        liquidity = 0.6 * spread_quality + 0.4 * depth_quality
        greeks_quality = sum(max(0.0, 100.0 - abs(abs(row.delta) - 0.40) * 100.0) for row in selected) / len(selected)
        iv_quality = sum(max(0.0, min(100.0, 100.0 - abs(row.implied_volatility - 0.35) * 100.0)) for row in selected) / len(selected)
        execution_quality = 0.7 * spread_quality + 0.3 * depth_quality
        overall = 0.35 * liquidity + 0.20 * spread_quality + 0.15 * greeks_quality + 0.10 * iv_quality + 0.20 * execution_quality
        return {
            "liquidity": round(liquidity, 2),
            "spread_quality": round(spread_quality, 2),
            "greeks_quality": round(greeks_quality, 2),
            "iv_quality": round(iv_quality, 2),
            "execution_quality": round(execution_quality, 2),
            "overall_contract_score": round(overall, 2),
        }

    def optimize(self, candidate: StrategyCandidate, rows: list[OptionContractRecord], spot: float, snapshot_id: str) -> ContractRecommendation:
        strategy = candidate.strategy.upper()
        calls = [x for x in rows if x.option_type == "CALL"]
        puts = [x for x in rows if x.option_type == "PUT"]
        legs: list[ContractLegRecommendation] = []
        reasons: list[str] = []
        try:
            if strategy == "LONG_CALL":
                legs = [self._leg(self._nearest(calls, target_delta=.55, target_dte=self.policy.target_dte), ContractSide.BUY)]
            elif strategy == "LONG_PUT":
                legs = [self._leg(self._nearest(puts, target_delta=-.55, target_dte=self.policy.target_dte), ContractSide.BUY)]
            elif strategy == "BULL_CALL_SPREAD":
                long = self._nearest(calls, target_delta=.55, target_dte=self.policy.target_dte)
                short = self._nearest((x for x in calls if x.expiry == long.expiry and x.strike > long.strike), target_delta=.30, target_dte=long.dte)
                legs = [self._leg(long, ContractSide.BUY), self._leg(short, ContractSide.SELL)]
            elif strategy == "BEAR_PUT_SPREAD":
                long = self._nearest(puts, target_delta=-.55, target_dte=self.policy.target_dte)
                short = self._nearest((x for x in puts if x.expiry == long.expiry and x.strike < long.strike), target_delta=-.30, target_dte=long.dte)
                legs = [self._leg(long, ContractSide.BUY), self._leg(short, ContractSide.SELL)]
            elif strategy == "BULL_PUT_SPREAD":
                short = self._nearest(puts, target_delta=-.30, target_dte=self.policy.target_dte)
                long = self._nearest((x for x in puts if x.expiry == short.expiry and x.strike < short.strike), target_delta=-.15, target_dte=short.dte)
                legs = [self._leg(long, ContractSide.BUY), self._leg(short, ContractSide.SELL)]
            elif strategy == "BEAR_CALL_SPREAD":
                short = self._nearest(calls, target_delta=.30, target_dte=self.policy.target_dte)
                long = self._nearest((x for x in calls if x.expiry == short.expiry and x.strike > short.strike), target_delta=.15, target_dte=short.dte)
                legs = [self._leg(short, ContractSide.SELL), self._leg(long, ContractSide.BUY)]
            elif strategy in {"CALL_DIAGONAL", "PUT_DIAGONAL", "CALL_CALENDAR", "PUT_CALENDAR"}:
                option_type = "CALL" if strategy.startswith("CALL") else "PUT"
                pool = calls if option_type == "CALL" else puts
                far = self._nearest(pool, target_delta=.55 if option_type == "CALL" else -.55, target_dte=self.policy.far_dte)
                if strategy.endswith("CALENDAR"):
                    near = self._nearest((x for x in pool if x.expiry < far.expiry), target_strike=far.strike, target_dte=self.policy.near_dte)
                else:
                    near = self._nearest((x for x in pool if x.expiry < far.expiry), target_delta=.30 if option_type == "CALL" else -.30, target_dte=self.policy.near_dte)
                legs = [self._leg(far, ContractSide.BUY), self._leg(near, ContractSide.SELL)]
            elif strategy == "IRON_CONDOR":
                short_put = self._nearest(puts, target_delta=-.35, target_dte=self.policy.target_dte)
                long_put = self._nearest((x for x in puts if x.expiry == short_put.expiry and x.strike < short_put.strike), target_delta=-.20, target_dte=short_put.dte)
                short_call = self._nearest((x for x in calls if x.expiry == short_put.expiry), target_delta=.35, target_dte=short_put.dte)
                long_call = self._nearest((x for x in calls if x.expiry == short_put.expiry and x.strike > short_call.strike), target_delta=.20, target_dte=short_put.dte)
                legs = [self._leg(long_put, ContractSide.BUY), self._leg(short_put, ContractSide.SELL), self._leg(short_call, ContractSide.SELL), self._leg(long_call, ContractSide.BUY)]
            elif strategy == "IRON_BUTTERFLY":
                atm_call = self._nearest(calls, target_strike=spot, target_dte=self.policy.target_dte)
                atm_put = self._nearest((x for x in puts if x.expiry == atm_call.expiry), target_strike=atm_call.strike, target_dte=atm_call.dte)
                long_put = self._nearest((x for x in puts if x.expiry == atm_call.expiry and x.strike < atm_put.strike), target_delta=-.20, target_dte=atm_call.dte)
                long_call = self._nearest((x for x in calls if x.expiry == atm_call.expiry and x.strike > atm_call.strike), target_delta=.20, target_dte=atm_call.dte)
                legs = [self._leg(long_put, ContractSide.BUY), self._leg(atm_put, ContractSide.SELL), self._leg(atm_call, ContractSide.SELL), self._leg(long_call, ContractSide.BUY)]
            else:
                raise ValueError(f"Unsupported strategy for contract optimization: {strategy}")
            symbols = [leg.option_symbol for leg in legs]
            if len(symbols) != len(set(symbols)):
                raise ValueError("Optimized multi-leg strategy reused an option contract")
            expiries = {leg.expiry for leg in legs}
            if strategy not in {"CALL_DIAGONAL", "PUT_DIAGONAL", "CALL_CALENDAR", "PUT_CALENDAR"} and len(expiries) != 1:
                raise ValueError("Same-expiry strategy produced inconsistent expirations")
            if strategy in {"CALL_DIAGONAL", "PUT_DIAGONAL", "CALL_CALENDAR", "PUT_CALENDAR"} and len(expiries) != 2:
                raise ValueError("Calendar/diagonal strategy requires distinct near and far expirations")
            executable = True
            reasons.extend(("EXACT_POLYGON_CONTRACT_IDENTITY", "LIQUIDITY_FILTERS_PASSED", "MULTI_LEG_CONSISTENCY_PASSED"))
        except Exception as exc:
            executable = False
            reasons.append(f"{type(exc).__name__}: {exc}")
            legs = []
        debit_credit = None
        slippage = None
        liquidity = None
        if legs:
            signed_mid = 0.0
            total_spread = 0.0
            liquidity_parts = []
            row_map = {r.option_symbol: r for r in rows}
            for leg in legs:
                row = row_map[leg.option_symbol]
                signed_mid += row.midpoint * (1 if leg.side == ContractSide.BUY else -1) * leg.quantity_ratio
                total_spread += max(0.0, row.ask - row.bid) * leg.quantity_ratio
                liquidity_parts.append(max(0.0, min(100.0, 100.0 * (1.0 - min(row.spread_pct, 1.0)) * .5 + min(row.open_interest / 20.0, 50.0))))
            debit_credit = round(signed_mid, 4)
            slippage = round(total_spread / 2.0, 4)
            liquidity = round(sum(liquidity_parts) / len(liquidity_parts), 2)
        rejection_reasons = tuple(reasons) if not executable else ()
        return ContractRecommendation(
            contract_recommendation_id=f"m62-contract-{uuid4().hex}",
            strategy_candidate_id=candidate.strategy_candidate_id,
            opportunity_id=candidate.opportunity_id,
            option_snapshot_id=snapshot_id,
            legs=tuple(legs), strategy=strategy, net_debit_credit=debit_credit, estimated_slippage=slippage,
            liquidity_score=liquidity, executable=executable, validation_reasons=tuple(reasons),
            rejection_reasons=rejection_reasons, optimization_scores=self._scorecard(legs, rows),
        )


class InstitutionalContractOptimizationService:
    def __init__(self, session: Session, policy: ContractOptimizationPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or ContractOptimizationPolicy()
        self.option_repository = PolygonPersistedOptionRepository(session, self.policy)
        self.optimizer = ExactPolygonContractOptimizer(self.policy)
        self.repository = InstitutionalOpportunityRepository(session)

    def optimize(self, opportunity_ids: list[str] | None = None, limit: int | None = None) -> ContractOptimizationResult:
        query = self.session.query(InstitutionalOpportunityModel).filter(
            InstitutionalOpportunityModel.state == OpportunityState.STRATEGIES_GENERATED.value
        )
        if opportunity_ids:
            query = query.filter(InstitutionalOpportunityModel.opportunity_id.in_(opportunity_ids))
        if limit:
            query = query.limit(limit)
        opportunities = query.all()
        optimized = failed = executable_count = non_executable_count = 0
        errors: list[str] = []
        for opportunity in opportunities:
            opportunity_id = opportunity.opportunity_id
            try:
                with self.session.begin_nested():
                    quote_date, spot, rows = self.option_repository.contracts(opportunity.symbol)
                    snapshot_id = f"polygon-options-{quote_date.isoformat()}"
                    candidates = self.session.query(StrategyCandidateModel).filter(
                        StrategyCandidateModel.opportunity_id == opportunity_id,
                        StrategyCandidateModel.disposition.in_((
                            StrategyDisposition.ELIGIBLE.value,
                            StrategyDisposition.SELECTED.value,
                        )),
                    ).order_by(StrategyCandidateModel.rank.asc().nullslast()).all()
                    if not candidates:
                        raise LookupError("No eligible strategy candidates found")
                    executable_for_opportunity = 0
                    for row in candidates:
                        candidate = StrategyCandidate(**row.payload_json)
                        if isinstance(candidate.disposition, str):
                            candidate = replace(candidate, disposition=StrategyDisposition(candidate.disposition))
                        recommendation = self.optimizer.optimize(candidate, rows, spot, snapshot_id)
                        self.repository.save_contract_recommendation(recommendation)
                        if recommendation.executable:
                            executable_count += 1
                            executable_for_opportunity += 1
                        else:
                            non_executable_count += 1
                    if executable_for_opportunity == 0:
                        raise ValueError("No executable contract recommendation generated")
                    opportunity.option_snapshot_id = snapshot_id
                    payload = dict(opportunity.payload_json or {})
                    lineage = dict(payload.get("lineage") or {})
                    lineage["option_snapshot_id"] = snapshot_id
                    lineage["option_snapshot_timestamp"] = quote_date.isoformat()
                    payload["lineage"] = lineage
                    opportunity.payload_json = payload
                    self.repository.transition(
                        opportunity_id,
                        OpportunityState.CONTRACTS_OPTIMIZED,
                        actor="m62_contract_optimization",
                        reason=f"Generated {executable_for_opportunity} executable exact Polygon contract recommendations",
                    )
                    optimized += 1
            except Exception as exc:
                failed += 1
                errors.append(f"{opportunity_id}: {type(exc).__name__}: {exc}")
        return ContractOptimizationResult(
            requested=len(opportunities), optimized=optimized, failed=failed,
            executable_recommendations=executable_count,
            non_executable_recommendations=non_executable_count,
            errors=tuple(errors),
        )
