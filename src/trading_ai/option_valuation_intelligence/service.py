from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from time import perf_counter
from math import ceil, isfinite
from statistics import mean, median
from uuid import uuid4

from sqlalchemy import desc, select

from trading_ai.institutional_options.models import (
    ContractRecommendationModel,
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
    StrategyCandidateModel,
)
from trading_ai.inflection_intelligence.models import InflectionPublicationModel, InflectionSnapshotModel
from trading_ai.institutional_market_structure.database_models import DealerPositionSnapshotModel
from trading_ai.market_intelligence.database_models import SectorMembershipModel

from .engine import InstitutionalOptionValuationEngine, deep_get, extract_legs, num, weighted_leg_value
from .context import build_relative_context, contract_features, event_context
from .market_inputs import MarketInputValidationError, preload_coherent_market_inputs
from .models import (OptionEdgeLedgerModel, OptionRelativeValueSnapshotModel, OptionValuationEventModel,
                     OptionValuationPublicationModel, OptionValuationSnapshotModel)


def percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values if isfinite(float(v)))
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered)-1, ceil(p*(len(ordered)-1))))
    return float(ordered[index])


class InstitutionalOptionValuationService:
    PUBLICATION = 'current_option_valuation_intelligence'

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.engine = InstitutionalOptionValuationEngine()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def build(
        self,
        *,
        limit: int | None = None,
        opportunity_ids: tuple[str, ...] | list[str] | None = None,
        scope: str = "CURRENT_RUN",
        max_workers: int = 4,
    ) -> dict:
        """Build governed valuations.

        Production ingestion must pass the current opportunity ids. Historical
        rebuilds may explicitly use ``scope="ALL"``. This keeps current-run
        work bounded while preserving every historical valuation snapshot.
        """
        started = perf_counter()
        normalized_ids = tuple(dict.fromkeys(opportunity_ids or ()))
        normalized_scope = str(scope or "CURRENT_RUN").upper()
        if normalized_scope not in {"CURRENT_RUN", "ALL"}:
            raise ValueError(f"Unsupported valuation scope: {scope}")
        if normalized_scope == "CURRENT_RUN" and not normalized_ids:
            raise ValueError(
                "CURRENT_RUN valuation requires explicit opportunity_ids; "
                "use scope='ALL' only for a governed historical rebuild"
            )
        with self.session_factory() as s:
            preload_started = perf_counter()
            compute_seconds = 0.0
            persist_seconds = 0.0
            q = select(ContractRecommendationModel).where(
                ContractRecommendationModel.executable.is_(True)
            )
            if normalized_scope == "CURRENT_RUN":
                q = q.where(ContractRecommendationModel.opportunity_id.in_(normalized_ids))
            q = q.order_by(desc(ContractRecommendationModel.created_at))
            raw_rows = s.execute(q).scalars().all()
            raw_recommendation_count = len(raw_rows)
            # A recommendation's historical executable flag is immutable audit
            # evidence, not current execution authority. Keep only the latest
            # recommendation for each exact opportunity/strategy lineage.
            latest_by_lineage = {}
            for recommendation in raw_rows:
                key = (recommendation.opportunity_id, recommendation.strategy_candidate_id)
                latest_by_lineage.setdefault(key, recommendation)
            rows = list(latest_by_lineage.values())
            deduplicated_recommendation_count = len(rows)
            if limit:
                rows = rows[:limit]
            now = self.now()
            valuation_run_id = f'M69-RUN-{uuid4().hex.upper()}'
            # Build governed cross-sectional relative-value context once for the run.
            opportunity_ids = sorted({r.opportunity_id for r in rows})
            opp_rows = s.execute(select(InstitutionalOpportunityModel).where(InstitutionalOpportunityModel.opportunity_id.in_(opportunity_ids))).scalars().all() if opportunity_ids else []
            opportunity_by_id = {o.opportunity_id:o for o in opp_rows}
            strategy_ids = sorted({r.strategy_candidate_id for r in rows})
            strategy_rows = s.execute(
                select(StrategyCandidateModel).where(
                    StrategyCandidateModel.strategy_candidate_id.in_(strategy_ids)
                )
            ).scalars().all() if strategy_ids else []
            strategy_by_id = {row.strategy_candidate_id: row for row in strategy_rows}
            rows = [
                row for row in rows
                if strategy_by_id.get(row.strategy_candidate_id) is not None
                and str(strategy_by_id[row.strategy_candidate_id].disposition).upper() != 'REJECTED'
            ]
            eligible_recommendation_count = len(rows)
            symbols = sorted({o.symbol for o in opp_rows})
            membership_rows = s.execute(select(SectorMembershipModel).where(SectorMembershipModel.symbol.in_(symbols), SectorMembershipModel.is_active.is_(True))).scalars().all() if symbols else []
            sector_by_symbol = {}
            sector_etf_by_symbol = {}
            for m in membership_rows:
                if m.symbol not in sector_by_symbol or m.effective_from > sector_by_symbol[m.symbol][0]:
                    sector_by_symbol[m.symbol]=(m.effective_from,m.sector or 'UNKNOWN')
                    sector_etf_by_symbol[m.symbol]=m.sector_etf
            sector_by_symbol={k:v[1] for k,v in sector_by_symbol.items()}
            features=[]
            coherent_by_contract = {}
            excluded_inputs = Counter()
            excluded_details = []
            actionable_rows = []

            # M68.2.1.15.8.1: preload mutable decision targets once. This
            # removes per-contract decision lookups while keeping all writes in
            # the single governed persistence transaction.
            contract_ids_for_run = [r.contract_recommendation_id for r in rows]
            decision_rows = s.execute(
                select(InstitutionalDecisionSnapshotModel).where(
                    InstitutionalDecisionSnapshotModel.contract_recommendation_id.in_(
                        contract_ids_for_run
                    )
                )
            ).scalars().all() if contract_ids_for_run else []
            decision_by_key = {
                (d.opportunity_id, d.strategy_candidate_id, d.contract_recommendation_id): d
                for d in decision_rows
            }
            coherent_requests = [
                (
                    cr.contract_recommendation_id,
                    opportunity_by_id[cr.opportunity_id].symbol,
                    dict(cr.payload_json or {}),
                )
                for cr in rows
                if cr.opportunity_id in opportunity_by_id
            ]
            coherent_bulk_started = perf_counter()
            coherent_by_contract, coherent_errors, coherent_preload_profile = preload_coherent_market_inputs(
                s, requests=coherent_requests
            )
            coherent_preload_seconds = round(perf_counter() - coherent_bulk_started, 6)
            for cr in rows:
                oo=opportunity_by_id.get(cr.opportunity_id)
                if oo:
                    coherent = coherent_by_contract.get(cr.contract_recommendation_id)
                    exc = coherent_errors.get(cr.contract_recommendation_id)
                    if coherent is None:
                        exc = exc or MarketInputValidationError(
                            'NO_COHERENT_MARKET_INPUT',
                            'bulk coherent-market preload produced no current input',
                        )
                        excluded_inputs[exc.code] += 1
                        excluded_details.append({
                            'contract_recommendation_id': cr.contract_recommendation_id,
                            'opportunity_id': cr.opportunity_id,
                            'symbol': oo.symbol,
                            'reason_code': exc.code,
                            'reason': str(exc),
                        })
                        decision = decision_by_key.get((
                            cr.opportunity_id,
                            cr.strategy_candidate_id,
                            cr.contract_recommendation_id,
                        ))
                        if decision:
                            decision_payload = dict(decision.payload_json or {})
                            decision_payload['option_valuation_intelligence'] = {
                                'status': 'NOT_ACTIONABLE',
                                'market_input_status': exc.code,
                                'reason': str(exc),
                                'valued_at': now,
                                'valuation_actionable': False,
                                'trade_execution_authority': False,
                            }
                            decision.payload_json = decision_payload
                        continue
                    actionable_rows.append(cr)
                    features.append(contract_features(
                        cr, oo.symbol, sector_by_symbol.get(oo.symbol,'UNKNOWN'),
                        coherent.underlying_price, payload_override=coherent.payload,
                    ))
            rows = actionable_rows
            relative_context=build_relative_context(features)
            feature_by_contract={x['contract_recommendation_id']:x for x in features}
            events=s.execute(select(OptionValuationEventModel).where(OptionValuationEventModel.status=='ACTIVE')).scalars().all()
            results = []
            coverage_counts = Counter()
            component_values = defaultdict(list)

            inf_pub = s.execute(
                select(InflectionPublicationModel).where(
                    InflectionPublicationModel.publication_name == 'current_institutional_inflection'
                )
            ).scalars().first()

            # Preload exact-current inflection and latest dealer evidence once.
            inflection_by_symbol = {}
            if inf_pub and symbols:
                inflection_rows = s.execute(
                    select(InflectionSnapshotModel).where(
                        InflectionSnapshotModel.publication_name
                        == 'current_institutional_inflection',
                        InflectionSnapshotModel.source_run_id == inf_pub.source_run_id,
                        InflectionSnapshotModel.symbol.in_(symbols),
                        InflectionSnapshotModel.timeframe == '1d',
                    ).order_by(
                        InflectionSnapshotModel.symbol,
                        desc(InflectionSnapshotModel.snapshot_timestamp),
                    )
                ).scalars().all()
                for ir in inflection_rows:
                    inflection_by_symbol.setdefault(ir.symbol, ir)

            dealer_by_symbol = {}
            if symbols:
                dealer_rows = s.execute(
                    select(DealerPositionSnapshotModel).where(
                        DealerPositionSnapshotModel.symbol.in_(symbols)
                    ).order_by(
                        DealerPositionSnapshotModel.symbol,
                        desc(DealerPositionSnapshotModel.as_of_date),
                    )
                ).scalars().all()
                for dealer_row in dealer_rows:
                    dealer_by_symbol.setdefault(dealer_row.symbol, dealer_row)

            # Existing valuations are also preloaded. The state hash is known
            # after pure compute, so keep all current candidate snapshots keyed
            # by (contract, state_hash) for deterministic single-writer reuse.
            actionable_contract_ids = [r.contract_recommendation_id for r in rows]
            existing_valuation_rows = s.execute(
                select(OptionValuationSnapshotModel).where(
                    OptionValuationSnapshotModel.contract_recommendation_id.in_(
                        actionable_contract_ids
                    )
                )
            ).scalars().all() if actionable_contract_ids else []
            existing_valuation_by_key = {
                (v.contract_recommendation_id, v.state_hash): v
                for v in existing_valuation_rows
            }

            siblings_by_opportunity = defaultdict(list)
            for candidate in rows:
                coherent_candidate = coherent_by_contract.get(
                    candidate.contract_recommendation_id
                )
                if coherent_candidate is not None:
                    siblings_by_opportunity[candidate.opportunity_id].append(
                        (candidate.contract_recommendation_id, coherent_candidate.payload)
                    )

            jobs = []
            for row in rows:
                opp = opportunity_by_id.get(row.opportunity_id)
                if not opp:
                    continue
                inf = None
                inflection_governance = {
                    'status': 'ABSTAIN',
                    'reason': 'NO_EXACT_CURRENT_INFLECTION_AUTHORITY',
                    'source_run_id': None if inf_pub is None else inf_pub.source_run_id,
                    'opportunity_stock_scanner_run_id': opp.stock_scanner_run_id,
                }
                if inf_pub and inf_pub.source_run_id == opp.stock_scanner_run_id:
                    ir = inflection_by_symbol.get(opp.symbol)
                    if (
                        ir is not None
                        and ir.coverage_status == 'CURRENT_EXACT'
                        and ir.disposition != 'ABSTAIN'
                    ):
                        inf = dict(ir.payload_json or {})
                        inflection_governance = {
                            'status': 'CURRENT_EXACT',
                            'reason': 'EXACT_SOURCE_RUN_AND_CURRENT_INPUTS',
                            'snapshot_id': ir.snapshot_id,
                            'source_run_id': ir.source_run_id,
                            'option_snapshot_id': ir.option_snapshot_id,
                        }
                    elif ir is not None:
                        inflection_governance = {
                            'status': 'ABSTAIN',
                            'reason': (
                                'INFLECTION_INPUTS_INCOMPLETE_OR_DISPOSITION_ABSTAIN'
                            ),
                            'snapshot_id': ir.snapshot_id,
                            'source_run_id': ir.source_run_id,
                            'coverage_status': ir.coverage_status,
                            'disposition': ir.disposition,
                        }

                siblings = [
                    payload
                    for contract_id, payload in siblings_by_opportunity.get(
                        row.opportunity_id, ()
                    )
                    if contract_id != row.contract_recommendation_id
                ]

                opportunity_payload = {
                    'direction': opp.direction,
                    **dict(opp.payload_json or {}),
                }
                coherent = coherent_by_contract[row.contract_recommendation_id]
                opportunity_payload['underlying_price'] = coherent.underlying_price
                opportunity_payload['underlying_price_date'] = (
                    coherent.market_date.isoformat()
                )

                dealer_snapshot = dealer_by_symbol.get(opp.symbol)
                if dealer_snapshot:
                    opportunity_payload['dealer_score'] = float(
                        dealer_snapshot.institutional_positioning_score
                    )
                    opportunity_payload['dealer_snapshot_date'] = str(
                        dealer_snapshot.as_of_date
                    )
                    opportunity_payload['gamma_regime'] = dealer_snapshot.gamma_regime
                    if (
                        not opportunity_payload.get('underlying_price')
                        and dealer_snapshot.spot_price
                    ):
                        opportunity_payload['underlying_price'] = float(
                            dealer_snapshot.spot_price
                        )

                feature = feature_by_contract.get(
                    row.contract_recommendation_id, {}
                )
                rv_context = relative_context.get(
                    row.contract_recommendation_id, {}
                )
                if rv_context.get('available'):
                    opportunity_payload['peer_implied_volatility'] = rv_context[
                        'peer_median_iv'
                    ]
                    opportunity_payload['relative_value_z_score'] = rv_context['z_score']
                    opportunity_payload['relative_value_regime'] = rv_context[
                        'relationship_regime'
                    ]
                    opportunity_payload['relative_value_peer_count'] = rv_context[
                        'peer_count'
                    ]
                    opportunity_payload['sector'] = feature.get('sector', 'UNKNOWN')
                    opportunity_payload['sector_etf'] = sector_etf_by_symbol.get(
                        opp.symbol
                    )
                iv_for_event = feature.get('iv') or 0.30
                ev_context = event_context(
                    opp.symbol,
                    opportunity_payload,
                    events,
                    iv_for_event,
                    coherent.market_date,
                )
                if ev_context.get('available'):
                    opportunity_payload['event_pricing_score'] = ev_context['score']
                    opportunity_payload['event_context'] = ev_context
                contract_payload = dict(coherent.payload)
                contract_payload['liquidity_score'] = row.liquidity_score
                strategy_row = strategy_by_id[row.strategy_candidate_id]
                jobs.append({
                    'row': row,
                    'opp': opp,
                    'inf': inf,
                    'inflection_governance': inflection_governance,
                    'siblings': siblings,
                    'opportunity_payload': opportunity_payload,
                    'contract_payload': contract_payload,
                    'feature': feature,
                    'rv_context': rv_context,
                    'ev_context': ev_context,
                    'strategy_row': strategy_row,
                })

            preload_seconds = round(perf_counter() - preload_started, 6)

            def _evaluate_job(job):
                # Pure computation only: no ORM/session objects are touched
                # beyond reading identifiers already materialized in memory.
                return InstitutionalOptionValuationEngine().evaluate(
                    opportunity=job['opportunity_payload'],
                    contract=job['contract_payload'],
                    inflection=job['inf'],
                    siblings=job['siblings'],
                )

            worker_count = max(1, int(max_workers or 1))
            compute_started = perf_counter()
            if worker_count > 1 and len(jobs) > 1:
                with ThreadPoolExecutor(
                    max_workers=min(worker_count, len(jobs)),
                    thread_name_prefix='m69-valuation',
                ) as executor:
                    computed_results = list(executor.map(_evaluate_job, jobs))
            else:
                computed_results = [_evaluate_job(job) for job in jobs]

            compute_seconds = round(perf_counter() - compute_started, 6)
            persist_started = perf_counter()

            # Deterministic single-writer phase. Persistence order is identical
            # to the pre-parallel row order and remains governed by one session.
            for job, result in zip(jobs, computed_results):
                row = job['row']
                opp = job['opp']
                feature = job['feature']
                rv_context = job['rv_context']
                ev_context = job['ev_context']
                strategy_row = job['strategy_row']
                contract_payload = job['contract_payload']
                result['inflection_governance'] = job['inflection_governance']
                result['valuation_run_id'] = valuation_run_id
                result['valued_at'] = now
                result['opportunity_id'] = row.opportunity_id
                result['contract_recommendation_id'] = row.contract_recommendation_id
                result['strategy_candidate_id'] = row.strategy_candidate_id
                result['strategy'] = strategy_row.strategy
                result['strategy_selected'] = bool(strategy_row.selected)
                result['recommendation_option_snapshot_id'] = row.option_snapshot_id
                result['legs'] = contract_payload.get('legs', [])
                result['valuation_actionable'] = True
                result['trade_execution_authority'] = bool(strategy_row.selected)
                result['relative_value'].update(rv_context)
                result['event_pricing'].update(ev_context)
                result['segmentation'] = {
                    'sector': feature.get('sector', 'UNKNOWN'),
                    'strategy': feature.get('strategy', 'UNKNOWN'),
                    'dte_bucket': feature.get('dte_bucket', 'UNKNOWN'),
                    'moneyness': feature.get('moneyness_bucket', 'UNKNOWN'),
                    'liquidity_bucket': (
                        'HIGH' if feature.get('liquidity', 0) >= 75
                        else ('MEDIUM' if feature.get('liquidity', 0) >= 50 else 'LOW')
                    ),
                    'right': feature.get('right', 'UNKNOWN'),
                }
                if rv_context.get('available'):
                    s.add(OptionRelativeValueSnapshotModel(
                        relative_value_id=f'M69-RV-{uuid4().hex.upper()}',
                        valuation_run_id=valuation_run_id,
                        contract_recommendation_id=row.contract_recommendation_id,
                        symbol=opp.symbol,
                        sector=feature.get('sector', 'UNKNOWN'),
                        peer_group=rv_context['peer_group'],
                        symbol_iv=rv_context['symbol_iv'],
                        peer_median_iv=rv_context['peer_median_iv'],
                        divergence_pct=rv_context['divergence_pct'],
                        z_score=rv_context['z_score'],
                        relationship_regime=rv_context['relationship_regime'],
                        snapshot_timestamp=now,
                        payload_json=rv_context,
                    ))

                existing = existing_valuation_by_key.get((
                    row.contract_recommendation_id,
                    result['state_hash'],
                ))
                if existing:
                    existing.classification = result['classification']
                    existing.market_mid = result['market_mid']
                    existing.fair_value = result['fair_value']
                    existing.mispricing_pct = result['mispricing_pct']
                    existing.edge_score = result['edge_score']
                    existing.confidence = result['confidence']
                    existing.stability_index = result['stability_index']
                    existing.snapshot_timestamp = now
                    existing.payload_json = result
                else:
                    existing = OptionValuationSnapshotModel(
                        snapshot_id=f'M69-VAL-{uuid4().hex.upper()}',
                        contract_recommendation_id=row.contract_recommendation_id,
                        opportunity_id=row.opportunity_id,
                        symbol=opp.symbol,
                        classification=result['classification'],
                        market_mid=result['market_mid'],
                        fair_value=result['fair_value'],
                        mispricing_pct=result['mispricing_pct'],
                        edge_score=result['edge_score'],
                        confidence=result['confidence'],
                        stability_index=result['stability_index'],
                        state_hash=result['state_hash'],
                        snapshot_timestamp=now,
                        payload_json=result,
                    )
                    s.add(existing)
                    s.add(OptionEdgeLedgerModel(
                        ledger_id=f'M69-EDGE-{uuid4().hex.upper()}',
                        contract_recommendation_id=row.contract_recommendation_id,
                        opportunity_id=row.opportunity_id,
                        state_hash=result['state_hash'],
                        observed_at=now,
                        payload_json=result,
                    ))

                cp = dict(row.payload_json or {})
                cp['option_valuation_intelligence'] = result
                row.payload_json = cp
                dp = decision_by_key.get((
                    row.opportunity_id,
                    row.strategy_candidate_id,
                    row.contract_recommendation_id,
                ))
                if dp:
                    payload = dict(dp.payload_json or {})
                    payload['option_valuation_intelligence'] = result
                    dp.payload_json = payload

                results.append(result)
                for name, meta in result['component_coverage'].items():
                    coverage_counts[
                        f'{name}:available' if meta['available'] else f'{name}:fallback'
                    ] += 1
                for name, value in result['components'].items():
                    component_values[name].append(float(value))

            persist_seconds = round(perf_counter() - persist_started, 6)

            mispricing = [float(r['mispricing_pct']) for r in results]
            raw_mispricing = [float(r.get('raw_executable_edge_pct', r['mispricing_pct'])) for r in results]
            edge_scores = [float(r['edge_score']) for r in results]
            execution_penalties = [abs(float(r['components']['execution_edge_pct'])) for r in results]
            class_counts = Counter(r['classification'] for r in results)
            histogram = {'<=-12': 0, '-12_to_-4': 0, '-4_to_4': 0, '4_to_12': 0, '>=12': 0}
            for value in mispricing:
                if value <= -12:
                    histogram['<=-12'] += 1
                elif value <= -4:
                    histogram['-12_to_-4'] += 1
                elif value < 4:
                    histogram['-4_to_4'] += 1
                elif value < 12:
                    histogram['4_to_12'] += 1
                else:
                    histogram['>=12'] += 1

            segmented={}
            for dimension in ('sector','strategy','dte_bucket','moneyness','liquidity_bucket','right'):
                buckets=defaultdict(list)
                for r in results:buckets[(r.get('segmentation') or {}).get(dimension,'UNKNOWN')].append(r)
                segmented[dimension]={}
                for key,vals in sorted(buckets.items(),key=lambda kv:str(kv[0])):
                    mp=[float(x['mispricing_pct']) for x in vals]
                    cc=Counter(x['classification'] for x in vals)
                    segmented[dimension][str(key)]={'count':len(vals),'median_mispricing_pct':round(median(mp),4) if mp else 0.0,'classification_counts':dict(cc),'average_edge_score':round(mean(float(x['edge_score']) for x in vals),4)}

            summary = {
                'valuation_run_id': valuation_run_id,
                'scope': normalized_scope,
                'requested_opportunity_count': len(normalized_ids),
                'raw_executable_history_count': raw_recommendation_count,
                'deduplicated_recommendation_count': deduplicated_recommendation_count,
                'eligible_current_lineage_count': eligible_recommendation_count,
                'requested_recommendation_count': eligible_recommendation_count,
                'built': len(results),
                'current_coherent_valuation_count': len(results),
                'excluded_market_input_count': sum(excluded_inputs.values()),
                'excluded_market_input_reasons': dict(excluded_inputs),
                'excluded_market_input_details': excluded_details[:500],
                'underpriced': class_counts['STRONG_UNDERPRICED'] + class_counts['MODERATELY_UNDERPRICED'],
                'overpriced': class_counts['STRONG_OVERPRICED'] + class_counts['MODERATELY_OVERPRICED'],
                'fair_value': class_counts['FAIR_VALUE'],
                'average_edge_score': round(mean(edge_scores), 4) if edge_scores else 0.0,
                'classification_counts': dict(class_counts),
                'parallel_profile': {
                    'execution_mode': (
                        'PARALLEL_PURE_COMPUTE_SINGLE_WRITER'
                        if worker_count > 1 and len(jobs) > 1
                        else 'SEQUENTIAL'
                    ),
                    'workers': min(worker_count, len(jobs)) if jobs else 0,
                    'preload_seconds': preload_seconds,
                    'coherent_market_preload_seconds': coherent_preload_seconds,
                    'coherent_market_preload': coherent_preload_profile,
                    'compute_seconds': compute_seconds,
                    'persist_seconds': persist_seconds,
                },
                'diagnostics': {
                    'mispricing_pct': {
                        'min': min(mispricing) if mispricing else 0,
                        'p05': percentile(mispricing, .05),
                        'p25': percentile(mispricing, .25),
                        'median': percentile(mispricing, .50),
                        'p75': percentile(mispricing, .75),
                        'p95': percentile(mispricing, .95),
                        'max': max(mispricing) if mispricing else 0,
                    },
                    'raw_mispricing_pct': {
                        'p01': percentile(raw_mispricing, .01),
                        'median': percentile(raw_mispricing, .50),
                        'p99': percentile(raw_mispricing, .99),
                    },
                    'histogram': histogram,
                    'component_average_edge_pct': {
                        k: round(mean(v), 4) if v else 0.0 for k, v in component_values.items()
                    },
                    'coverage_counts': dict(coverage_counts),
                    'average_component_coverage_pct': round(
                        mean([r['component_coverage_pct'] for r in results]), 4
                    ) if results else 0.0,
                    'near_moderate_threshold_count': sum(1 for v in mispricing if 3 <= abs(v) < 4),
                    'near_strong_threshold_count': sum(1 for v in mispricing if 10 <= abs(v) < 12),
                    'low_net_premium_count': sum(1 for r in results if r.get('low_net_premium')),
                    'execution_penalty_pct': {
                        'median': percentile(execution_penalties, .50),
                        'p95': percentile(execution_penalties, .95),
                        'max': max(execution_penalties) if execution_penalties else 0.0,
                    },
                    'independent_model_count': sum(
                        1 for r in results if r.get('valuation_basis') == 'INDEPENDENT_MODEL'
                    ),
                    'relative_value_available_count': sum(1 for r in results if (r.get('relative_value') or {}).get('available')),
                    'event_available_count': sum(1 for r in results if (r.get('event_pricing') or {}).get('available')),
                    'event_modeled_count': sum(1 for r in results if (r.get('event_pricing') or {}).get('expected_move_pct') is not None),
                    'segmented': segmented,
                },
            }

            spread = summary['diagnostics']['mispricing_pct']['p95'] - summary['diagnostics']['mispricing_pct']['p05']
            coverage = summary['diagnostics']['average_component_coverage_pct']
            independent = summary['diagnostics']['independent_model_count']
            one_sided_count = max(summary['underpriced'], summary['overpriced'])
            one_sided_ratio = one_sided_count / len(results) if results else 0.0
            distribution_anomaly = len(results) >= 30 and one_sided_ratio >= 0.95
            summary['diagnostics']['one_sided_classification_ratio'] = round(one_sided_ratio, 6)
            summary['diagnostics']['distribution_anomaly'] = distribution_anomaly
            coherent_complete = not excluded_inputs
            status = 'READY' if (
                results and coherent_complete and not distribution_anomaly
                and coverage >= 45 and independent == len(results) and spread >= 1.0
            ) else (
                'DEGRADED' if results else 'FAILED'
            )

            pub = s.execute(
                select(OptionValuationPublicationModel).where(
                    OptionValuationPublicationModel.publication_name == self.PUBLICATION
                )
            ).scalars().first()
            if pub:
                pub.status = status
                pub.contract_count = len(results)
                pub.underpriced_count = summary['underpriced']
                pub.overpriced_count = summary['overpriced']
                pub.published_at = now
                pub.payload_json = summary
            else:
                s.add(OptionValuationPublicationModel(
                    publication_id=f'M69-PUB-{uuid4().hex.upper()}',
                    publication_name=self.PUBLICATION,
                    status=status,
                    contract_count=len(results),
                    underpriced_count=summary['underpriced'],
                    overpriced_count=summary['overpriced'],
                    published_at=now,
                    payload_json=summary,
                ))
            s.commit()
            duration = round(perf_counter() - started, 4)
            summary['duration_seconds'] = duration
            summary['valuations_per_second'] = round(len(results) / duration, 4) if duration > 0 else 0.0
            return {'status': status, 'published_at': now, **summary}

    def current(self, limit=100):
        with self.session_factory() as s:
            pub = s.execute(
                select(OptionValuationPublicationModel).where(
                    OptionValuationPublicationModel.publication_name == self.PUBLICATION
                )
            ).scalars().first()
            run_id = ((pub.payload_json or {}).get('valuation_run_id') if pub else None)
            rows = s.execute(
                select(OptionValuationSnapshotModel).order_by(
                    desc(OptionValuationSnapshotModel.snapshot_timestamp),
                    desc(OptionValuationSnapshotModel.edge_score),
                )
            ).scalars().all()
            if run_id:
                rows = [r for r in rows if (r.payload_json or {}).get('valuation_run_id') == run_id]
            rows = rows[:limit]
            return {
                'publication': None if not pub else {
                    'status': pub.status,
                    'published_at': pub.published_at,
                    'payload': pub.payload_json,
                },
                'snapshots': [
                    r.payload_json | {
                        'symbol': r.symbol,
                        'opportunity_id': r.opportunity_id,
                        'contract_recommendation_id': r.contract_recommendation_id,
                    }
                    for r in rows
                ],
            }
