from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from math import isfinite
from statistics import median
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

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
from .models import (
    InstitutionalOpportunityModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
)
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
    strategy_quality_weight: float = 0.65
    contract_quality_weight: float = 0.35
    policy_version: str = "M68.2.1.13-GLOBAL-FEASIBLE-PACKAGE-1.0"


@dataclass(frozen=True)
class ContractOptimizationResult:
    requested: int
    optimized: int
    failed: int
    executable_recommendations: int
    non_executable_recommendations: int
    errors: tuple[str, ...] = ()
    parallel_workers: int = 1
    execution_mode: str = "SEQUENTIAL"


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
    implied_volatility: float | None
    raw_implied_volatility: float | None = None
    implied_volatility_status: str = "SOURCE"
    implied_volatility_source: str = "POLYGON_PERSISTED"
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    quote_timestamp: str | None = None
    source_underlying_price: float | None = None

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


def normalize_implied_volatility_records(records: list[OptionContractRecord]) -> list[OptionContractRecord]:
    """Return records with explicit IV provenance and deterministic chain fallback.

    Polygon IV is stored as a decimal (0.98 == 98%). Missing values and isolated
    extreme values are not allowed to collapse to a silent 1% pricing floor.
    """
    credible = [float(x.raw_implied_volatility) for x in records if x.raw_implied_volatility is not None and 0.03 <= float(x.raw_implied_volatility) <= 3.0]
    chain_median = median(credible) if credible else None
    normalized: list[OptionContractRecord] = []
    for item in records:
        raw = item.raw_implied_volatility
        status = item.implied_volatility_status
        effective = item.implied_volatility
        if raw is None or raw <= 0:
            status = "MISSING_CHAIN_MEDIAN_FALLBACK" if chain_median is not None else "MISSING"
            effective = chain_median
        elif chain_median is not None and (raw < max(0.03, chain_median * 0.20) or raw > min(3.0, chain_median * 5.0)):
            status = "ANOMALOUS_CHAIN_MEDIAN_FALLBACK"
            effective = chain_median
        normalized.append(replace(item, implied_volatility=effective, implied_volatility_status=status))
    return normalized


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
            source_timestamp = getattr(row, "quote_timestamp", None)
            try:
                market_quote_date = datetime.fromisoformat(
                    str(source_timestamp).replace("Z", "+00:00")
                ).date() if source_timestamp else quote_date
            except ValueError:
                market_quote_date = quote_date
            contract = OptionContractRecord(
                option_symbol=str(row.option_symbol or "").strip(),
                quote_date=market_quote_date,
                expiry=row.expiry,
                option_type=option_type,
                strike=float(row.strike),
                bid=max(0.0, float(row.bid or 0.0)),
                ask=max(0.0, float(row.ask or 0.0)),
                last=max(0.0, float(row.last or 0.0)),
                volume=max(0, int(row.volume or 0)),
                open_interest=max(0, int(row.open_interest or 0)),
                implied_volatility=(None if row.implied_volatility is None else max(0.0, float(row.implied_volatility))),
                raw_implied_volatility=(None if row.implied_volatility is None else max(0.0, float(row.implied_volatility))),
                implied_volatility_status=("MISSING" if row.implied_volatility is None or float(row.implied_volatility or 0.0) <= 0 else "SOURCE"),
                delta=float(row.delta or 0.0), gamma=float(row.gamma or 0.0), theta=float(row.theta or 0.0), vega=float(row.vega or 0.0),
                quote_timestamp=getattr(row, "quote_timestamp", None),
                source_underlying_price=getattr(row, "source_underlying_price", None),
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

        # M76.2.3: normalize IV with explicit provenance after quote/liquidity filtering.
        return quote_date, spot, normalize_implied_volatility_records(result)


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
            implied_volatility_raw=row.raw_implied_volatility,
            implied_volatility_status=row.implied_volatility_status,
            implied_volatility_source=row.implied_volatility_source,
            delta=row.delta, gamma=row.gamma, theta=row.theta, vega=row.vega,
            dte=row.dte, quote_date=row.quote_date.isoformat(),
            quote_timestamp=row.quote_timestamp,
            source_underlying_price=row.source_underlying_price,
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
        usable_ivs = [float(row.implied_volatility) for row in selected if row.implied_volatility is not None and row.implied_volatility > 0]
        iv_quality = (sum(max(0.0, min(100.0, 100.0 - abs(iv - 0.35) * 100.0)) for iv in usable_ivs) / len(usable_ivs)) if usable_ivs else 0.0
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
            market_data_as_of=(rows[0].quote_date.isoformat() if rows else None),
            underlying_price=spot,
        )


class InstitutionalContractOptimizationService:
    def __init__(self, session: Session, policy: ContractOptimizationPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or ContractOptimizationPolicy()
        self.option_repository = PolygonPersistedOptionRepository(session, self.policy)
        self.optimizer = ExactPolygonContractOptimizer(self.policy)
        self.repository = InstitutionalOpportunityRepository(session)

    def optimize(
        self,
        opportunity_ids: list[str] | None = None,
        limit: int | None = None,
        *,
        max_workers: int = 4,
    ) -> ContractOptimizationResult:
        query = self.session.query(InstitutionalOpportunityModel).filter(
            InstitutionalOpportunityModel.state == OpportunityState.STRATEGIES_GENERATED.value
        )
        if opportunity_ids:
            query = query.filter(InstitutionalOpportunityModel.opportunity_id.in_(opportunity_ids))
        if limit:
            query = query.limit(limit)
        opportunities = query.all()

        # M68.2.1.15.8.1: opportunity-isolated parallelism. Each worker owns
        # its own SQLAlchemy Session and processes exactly one opportunity.
        # SQLite remains sequential because its write-locking model is not a
        # valid proxy for PostgreSQL production concurrency. executor.map keeps
        # aggregation deterministic in the original query order.
        worker_count = max(1, int(max_workers or 1))
        bind = self.session.get_bind()
        if (
            worker_count > 1
            and len(opportunities) > 1
            and getattr(getattr(bind, "dialect", None), "name", None) != "sqlite"
        ):
            opportunity_order = [str(o.opportunity_id) for o in opportunities]
            factory = sessionmaker(bind=bind, expire_on_commit=False)

            def _worker(opportunity_id: str) -> ContractOptimizationResult:
                with factory() as worker_session:
                    worker_service = InstitutionalContractOptimizationService(
                        worker_session, self.policy
                    )
                    result = worker_service.optimize(
                        opportunity_ids=[opportunity_id],
                        limit=1,
                        max_workers=1,
                    )
                    worker_session.commit()
                    return result

            with ThreadPoolExecutor(
                max_workers=min(worker_count, len(opportunity_order)),
                thread_name_prefix="m62-contract",
            ) as executor:
                worker_results = list(executor.map(_worker, opportunity_order))

            return ContractOptimizationResult(
                requested=sum(r.requested for r in worker_results),
                optimized=sum(r.optimized for r in worker_results),
                failed=sum(r.failed for r in worker_results),
                executable_recommendations=sum(
                    r.executable_recommendations for r in worker_results
                ),
                non_executable_recommendations=sum(
                    r.non_executable_recommendations for r in worker_results
                ),
                errors=tuple(
                    error
                    for result in worker_results
                    for error in result.errors
                ),
                parallel_workers=min(worker_count, len(opportunity_order)),
                execution_mode="PARALLEL_OPPORTUNITY_ISOLATED",
            )

        optimized = failed = executable_count = non_executable_count = 0
        errors: list[str] = []
        for opportunity in opportunities:
            opportunity_id = opportunity.opportunity_id
            opportunity_executable_count = 0
            opportunity_non_executable_count = 0
            try:
                with self.session.begin_nested():
                    quote_date, spot, rows = self.option_repository.contracts(opportunity.symbol)
                    snapshot_id = f"polygon-options-{quote_date.isoformat()}"
                    comparison = (
                        self.session.query(StrategyComparisonModel)
                        .filter_by(opportunity_id=opportunity_id)
                        .one_or_none()
                    )
                    selected_strategy_candidate_id = (
                        None if comparison is None
                        else comparison.selected_strategy_candidate_id
                    )
                    candidates = self.session.query(StrategyCandidateModel).filter(
                        StrategyCandidateModel.opportunity_id == opportunity_id,
                        StrategyCandidateModel.disposition.in_((
                            StrategyDisposition.ELIGIBLE.value,
                            StrategyDisposition.SELECTED.value,
                        )),
                    ).order_by(StrategyCandidateModel.rank.asc().nullslast()).all()
                    if not candidates:
                        raise LookupError("No eligible strategy candidates found")
                    if comparison is None:
                        raise LookupError("Current strategy comparison is missing")

                    # The strategy-stage winner is provisional.  Exact option
                    # packages are built for every eligible strategy before any
                    # executable authority is selected.  This prevents an
                    # unbuildable first-ranked strategy from stranding a better
                    # feasible package.
                    provisional_selected_id = (
                        str(selected_strategy_candidate_id)
                        if selected_strategy_candidate_id
                        else None
                    )
                    packages: list[dict[str, Any]] = []
                    for row in candidates:
                        candidate = StrategyCandidate(**row.payload_json)
                        if isinstance(candidate.disposition, str):
                            candidate = replace(candidate, disposition=StrategyDisposition(candidate.disposition))
                        recommendation = self.optimizer.optimize(candidate, rows, spot, snapshot_id)
                        canonical_recommendation_id = (
                            self.repository.save_contract_recommendation(
                                recommendation
                            )
                        )
                        if recommendation.executable:
                            opportunity_executable_count += 1
                        else:
                            opportunity_non_executable_count += 1
                        contract_score = float(
                            recommendation.optimization_scores.get(
                                "overall_contract_score", 0.0
                            )
                        )
                        package_score = (
                            float(candidate.eligibility_score)
                            * self.policy.strategy_quality_weight
                            + contract_score
                            * self.policy.contract_quality_weight
                        )
                        packages.append({
                            "row": row,
                            "candidate": candidate,
                            "recommendation": recommendation,
                            "canonical_recommendation_id": (
                                canonical_recommendation_id
                            ),
                            "contract_score": round(contract_score, 6),
                            "package_score": round(package_score, 6),
                        })

                    ranked_packages = sorted(
                        packages,
                        key=lambda item: (
                            0 if item["recommendation"].executable else 1,
                            -item["package_score"],
                            -item["contract_score"],
                            -float(item["recommendation"].liquidity_score or 0.0),
                            float(item["recommendation"].estimated_slippage or 0.0),
                            int(item["candidate"].rank or 1_000_000),
                            str(item["candidate"].strategy),
                            str(item["candidate"].strategy_candidate_id),
                        ),
                    )
                    feasible_packages = [
                        item for item in ranked_packages
                        if item["recommendation"].executable
                    ]
                    if not feasible_packages:
                        raise ValueError(
                            "No executable contract recommendation generated "
                            "for any eligible strategy after exhaustive "
                            f"package evaluation; evaluated={len(packages)}"
                        )
                    selected_package = feasible_packages[0]
                    selected_strategy_candidate_id = str(
                        selected_package["candidate"].strategy_candidate_id
                    )

                    package_ledger: list[dict[str, Any]] = []
                    for package_rank, item in enumerate(ranked_packages, 1):
                        candidate = item["candidate"]
                        recommendation = item["recommendation"]
                        is_selected = (
                            str(candidate.strategy_candidate_id)
                            == selected_strategy_candidate_id
                        )
                        candidate_row = item["row"]
                        candidate_row.selected = is_selected
                        candidate_row.disposition = (
                            StrategyDisposition.SELECTED.value
                            if is_selected
                            else StrategyDisposition.ELIGIBLE.value
                        )
                        candidate_payload = dict(candidate_row.payload_json or {})
                        candidate_payload["selected"] = is_selected
                        candidate_payload["disposition"] = candidate_row.disposition
                        candidate_metadata = dict(
                            candidate_payload.get("metadata") or {}
                        )
                        candidate_metadata["contract_feasibility_authority"] = {
                            "policy_version": self.policy.policy_version,
                            "option_snapshot_id": snapshot_id,
                            "package_rank": package_rank,
                            "package_score": item["package_score"],
                            "contract_score": item["contract_score"],
                            "executable": bool(recommendation.executable),
                            "selected": is_selected,
                        }
                        candidate_payload["metadata"] = candidate_metadata
                        candidate_row.payload_json = candidate_payload
                        package_ledger.append({
                            "package_rank": package_rank,
                            "strategy_candidate_id": str(
                                candidate.strategy_candidate_id
                            ),
                            "strategy": str(candidate.strategy),
                            "strategy_rank": candidate.rank,
                            "strategy_eligibility_score": round(
                                float(candidate.eligibility_score), 6
                            ),
                            "contract_recommendation_id": str(
                                item["canonical_recommendation_id"]
                            ),
                            "executable": bool(recommendation.executable),
                            "contract_score": item["contract_score"],
                            "liquidity_score": recommendation.liquidity_score,
                            "estimated_slippage": (
                                recommendation.estimated_slippage
                            ),
                            "package_score": item["package_score"],
                            "selected": is_selected,
                            "rejection_reasons": list(
                                recommendation.rejection_reasons
                            ),
                        })

                    comparison.selected_strategy_candidate_id = (
                        selected_strategy_candidate_id
                    )
                    comparison.policy_version = self.policy.policy_version
                    comparison.created_at = datetime.now(
                        timezone.utc
                    ).isoformat()
                    comparison_payload = dict(comparison.payload_json or {})
                    comparison_payload.update({
                        "selected_strategy_candidate_id": (
                            selected_strategy_candidate_id
                        ),
                        "ranked_strategy_candidate_ids": [
                            item["strategy_candidate_id"]
                            for item in package_ledger
                        ],
                        "comparison_policy_version": (
                            self.policy.policy_version
                        ),
                        "selection_stage": (
                            "EXHAUSTIVE_EXECUTABLE_PACKAGE_AUTHORITY"
                        ),
                        "contract_feasibility_authority": {
                            "version": (
                                "M68.2.1.13-GLOBAL-FEASIBLE-PACKAGE-1.0"
                            ),
                            "status": "PROVEN",
                            "option_snapshot_id": snapshot_id,
                            "provisional_strategy_candidate_id": (
                                provisional_selected_id
                            ),
                            "selected_strategy_candidate_id": (
                                selected_strategy_candidate_id
                            ),
                            "eligible_strategy_count": len(packages),
                            "executable_package_count": len(
                                feasible_packages
                            ),
                            "all_eligible_strategies_evaluated": True,
                            "higher_ranked_feasible_excluded": 0,
                            "objective": (
                                "MAXIMIZE_STRATEGY_AND_CONTRACT_QUALITY"
                            ),
                            "weights": {
                                "strategy_quality": (
                                    self.policy.strategy_quality_weight
                                ),
                                "contract_quality": (
                                    self.policy.contract_quality_weight
                                ),
                            },
                            "package_ranking": package_ledger,
                        },
                    })
                    comparison.payload_json = comparison_payload
                    opportunity.option_snapshot_id = snapshot_id
                    payload = dict(opportunity.payload_json or {})
                    lineage = dict(payload.get("lineage") or {})
                    lineage["option_snapshot_id"] = snapshot_id
                    lineage["contract_option_snapshot_id"] = snapshot_id
                    lineage["option_snapshot_timestamp"] = quote_date.isoformat()
                    payload["lineage"] = lineage
                    metadata = dict(payload.get("metadata") or {})
                    metadata["contract_option_snapshot_id"] = snapshot_id
                    metadata["m68_2_1_13_global_feasible_package_proven"] = True
                    metadata["m68_2_1_13_selected_strategy_candidate_id"] = (
                        selected_strategy_candidate_id
                    )
                    metadata["m68_2_1_13_executable_package_count"] = (
                        len(feasible_packages)
                    )
                    payload["metadata"] = metadata
                    opportunity.payload_json = payload
                    self.repository.transition(
                        opportunity_id,
                        OpportunityState.CONTRACTS_OPTIMIZED,
                        actor="m62_contract_optimization",
                        reason=(
                            "Generated an executable exact Polygon package "
                            "after exhaustive eligible-strategy evaluation; "
                            f"selected={selected_strategy_candidate_id}; "
                            f"total_executable={opportunity_executable_count}"
                        ),
                    )
                optimized += 1
                executable_count += opportunity_executable_count
                non_executable_count += opportunity_non_executable_count
            except Exception as exc:
                failed += 1
                errors.append(f"{opportunity_id}: {type(exc).__name__}: {exc}")
        return ContractOptimizationResult(
            requested=len(opportunities), optimized=optimized, failed=failed,
            executable_recommendations=executable_count,
            non_executable_recommendations=non_executable_count,
            errors=tuple(errors),
        )
