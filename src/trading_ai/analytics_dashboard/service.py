from __future__ import annotations

from collections import Counter, defaultdict
from math import ceil
from statistics import mean
from typing import Any, Iterable

from sqlalchemy import desc, select

from trading_ai.inflection_intelligence.models import InflectionPublicationModel, InflectionSnapshotModel
from trading_ai.institutional_options.models import (
    ContractRecommendationModel,
    InstitutionalOpportunityModel,
    OpportunityThesisModel,
    StrategyCandidateModel,
    StrategyValuationModel,
)
from trading_ai.market_intelligence.database_models import SectorMembershipModel
from trading_ai.option_valuation_intelligence.models import OptionValuationPublicationModel, OptionValuationSnapshotModel


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _deep(payload: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(payload, dict):
        return default
    for key in keys:
        value: Any = payload
        ok = True
        for part in key.split('.'):
            if not isinstance(value, dict) or part not in value:
                ok = False
                break
            value = value[part]
        if ok and value not in (None, ''):
            return value
    return default


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, ceil((p / 100.0) * len(ordered)) - 1))
    return round(ordered[index], 4)


def _histogram(values: Iterable[float], step: int = 10, minimum: int = 0, maximum: int = 100) -> list[dict[str, Any]]:
    buckets = []
    vals = list(values)
    for lo in range(minimum, maximum, step):
        hi = lo + step
        count = sum(lo <= value < hi for value in vals)
        if hi == maximum:
            count += sum(value == maximum for value in vals)
        buckets.append({'label': f'{lo}-{hi}', 'minimum': lo, 'maximum': hi, 'count': count})
    return buckets


def _distribution(values: Iterable[str]) -> list[dict[str, Any]]:
    counts = Counter(str(value or 'UNKNOWN') for value in values)
    total = sum(counts.values()) or 1
    return [
        {'name': name, 'count': count, 'percentage': round(count / total * 100.0, 2)}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


class AnalyticsDashboardService:
    HIGH_CONVICTION_THRESHOLD = 80.0

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def inflection(self, *, limit: int = 1000) -> dict[str, Any]:
        with self.session_factory() as session:
            publication = session.execute(
                select(InflectionPublicationModel)
                .where(InflectionPublicationModel.publication_name == 'current_institutional_inflection')
                .order_by(desc(InflectionPublicationModel.published_at))
            ).scalars().first()
            if not publication:
                return {'status': 'NOT_AVAILABLE', 'summary': {}, 'candidates': []}

            rows = session.execute(
                select(InflectionSnapshotModel)
                .where(
                    InflectionSnapshotModel.publication_name == publication.publication_name,
                    InflectionSnapshotModel.source_run_id == publication.source_run_id,
                )
                .order_by(desc(InflectionSnapshotModel.inflection_score))
                .limit(limit)
            ).scalars().all()

            symbols = [row.symbol for row in rows]
            opportunities = session.execute(
                select(InstitutionalOpportunityModel)
                .where(InstitutionalOpportunityModel.symbol.in_(symbols))
                .order_by(desc(InstitutionalOpportunityModel.updated_at))
            ).scalars().all() if symbols else []
            opportunity_by_symbol = {}
            for opportunity in opportunities:
                current = opportunity_by_symbol.get(opportunity.symbol)
                if current is None:
                    opportunity_by_symbol[opportunity.symbol] = opportunity
                    continue
                current_exact = current.stock_scanner_run_id == publication.source_run_id
                candidate_exact = opportunity.stock_scanner_run_id == publication.source_run_id
                if candidate_exact and not current_exact:
                    opportunity_by_symbol[opportunity.symbol] = opportunity
            opportunity_ids = [row.opportunity_id for row in opportunity_by_symbol.values()]
            theses = session.execute(
                select(OpportunityThesisModel).where(OpportunityThesisModel.opportunity_id.in_(opportunity_ids))
            ).scalars().all() if opportunity_ids else []
            thesis_by_opportunity = {row.opportunity_id: row for row in theses}
            strategy_rows = session.execute(
                select(StrategyCandidateModel).where(
                    StrategyCandidateModel.opportunity_id.in_(opportunity_ids),
                    StrategyCandidateModel.selected.is_(True),
                )
            ).scalars().all() if opportunity_ids else []
            strategy_by_opportunity = {row.opportunity_id: row for row in strategy_rows}
            memberships = session.execute(
                select(SectorMembershipModel).where(
                    SectorMembershipModel.symbol.in_(symbols),
                    SectorMembershipModel.is_active.is_(True),
                )
            ).scalars().all() if symbols else []
            membership_by_symbol = {}
            for membership in memberships:
                current = membership_by_symbol.get(membership.symbol)
                if current is None or membership.effective_from > current.effective_from:
                    membership_by_symbol[membership.symbol] = membership

            candidates: list[dict[str, Any]] = []
            component_values: dict[str, list[float]] = defaultdict(list)
            for row in rows:
                payload = dict(row.payload_json or {})
                components = _deep(payload, 'components', default={}) or {}
                for name, value in components.items():
                    if isinstance(value, (int, float)):
                        component_values[str(name)].append(float(value))
                opportunity = opportunity_by_symbol.get(row.symbol)
                op_payload = dict(opportunity.payload_json or {}) if opportunity else {}
                thesis = thesis_by_opportunity.get(opportunity.opportunity_id) if opportunity else None
                thesis_payload = dict(thesis.payload_json or {}) if thesis else {}
                membership = membership_by_symbol.get(row.symbol)
                strategy_row = strategy_by_opportunity.get(opportunity.opportunity_id) if opportunity else None
                sector = (membership.sector if membership and membership.sector else None) or _deep(
                    payload, 'sector', 'context.sector', 'stock_payload.sector',
                    'stock_payload.context.sector', default=None
                )
                if not sector:
                    sector = _deep(
                        op_payload, 'sector', 'stock_candidate.sector', 'source_payload.sector',
                        'source_payload.context.sector', default='NOT_CLASSIFIED'
                    )
                strategy = strategy_row.strategy if strategy_row else _deep(
                    op_payload, 'selected_strategy', 'strategy', 'strategy_name', default='NOT_EVALUATED'
                )
                regime = _deep(
                    thesis_payload, 'market_regime', 'context.market_regime', default=None
                ) or _deep(
                    payload, 'market_regime', 'context.market_regime', 'stock_payload.market_regime',
                    'stock_payload.context.market_regime', default=None
                )
                if not regime:
                    regime = _deep(
                        op_payload, 'market_regime', 'source_payload.market_regime',
                        'source_payload.context.market_regime', default='NOT_AVAILABLE'
                    )
                score = float(row.inflection_score)
                candidates.append({
                    'snapshot_id': row.snapshot_id,
                    'symbol': row.symbol,
                    'timeframe': row.timeframe,
                    'direction': row.direction,
                    'transition_state': row.transition_state,
                    'score': score,
                    'confidence': float(row.confidence),
                    'sector': str(sector or 'NOT_CLASSIFIED'),
                    'industry': str(membership.industry or '') if membership else '',
                    'company_name': str(membership.company_name or '') if membership else '',
                    'asset_class': opportunity.asset_class if opportunity else None,
                    'opportunity_id': opportunity.opportunity_id if opportunity else None,
                    'opportunity_state': opportunity.state if opportunity else 'NOT_MATERIALIZED',
                    'opportunity_category': opportunity.category if opportunity else None,
                    'opportunity_score': float(opportunity.overall_score) if opportunity else None,
                    'conviction': opportunity.conviction if opportunity else None,
                    'strategy': str(strategy or 'NOT_EVALUATED'),
                    'market_regime': str(regime or 'NOT_AVAILABLE'),
                    'primary_timeframe': thesis.primary_timeframe if thesis else row.timeframe,
                    'invalidation_level': float(thesis.invalidation_level) if thesis else None,
                    'entry_zone_low': float(thesis.entry_zone_low) if thesis else None,
                    'entry_zone_high': float(thesis.entry_zone_high) if thesis else None,
                    'option_snapshot_id': opportunity.option_snapshot_id if opportunity else None,
                    'threshold_gap': round(max(0.0, self.HIGH_CONVICTION_THRESHOLD - score), 4),
                    'near_high_conviction': self.HIGH_CONVICTION_THRESHOLD - 10 <= score < self.HIGH_CONVICTION_THRESHOLD,
                    'components': components,
                    'evidence': _deep(payload, 'evidence', default=[]),
                    'conflicting_evidence': _deep(payload, 'conflicting_evidence', default=[]),
                    'snapshot_timestamp': row.snapshot_timestamp,
                    'source_run_id': row.source_run_id,
                })

            scores = [row['score'] for row in candidates]
            threshold_bands = [
                {'name': 'Within 2 points', 'minimum': 78, 'maximum': 80, 'count': sum(78 <= score < 80 for score in scores)},
                {'name': 'Within 5 points', 'minimum': 75, 'maximum': 80, 'count': sum(75 <= score < 80 for score in scores)},
                {'name': 'Within 10 points', 'minimum': 70, 'maximum': 80, 'count': sum(70 <= score < 80 for score in scores)},
            ]
            summary = {
                'symbols_analyzed': len(candidates),
                'average_score': round(mean(scores), 4) if scores else 0.0,
                'median_score': _percentile(scores, 50),
                'high_conviction': sum(score >= 80 for score in scores),
                'actionable': sum(70 <= score < 80 for score in scores),
                'watch': sum(60 <= score < 70 for score in scores),
                'below_watch': sum(score < 60 for score in scores),
                'published_at': publication.published_at,
                'publication_id': publication.publication_id,
                'source_run_id': publication.source_run_id,
                'status': publication.status,
            }
            return {
                'status': 'READY',
                'summary': summary,
                'histogram': _histogram(scores),
                'percentiles': {f'p{p}': _percentile(scores, p) for p in (10, 25, 50, 75, 90, 95, 99)},
                'thresholds': {'high_conviction': 80, 'actionable': 70, 'watch': 60},
                'near_threshold': threshold_bands,
                'by_transition_state': _distribution(row['transition_state'] for row in candidates),
                'by_sector': _distribution(row['sector'] for row in candidates),
                'by_strategy': _distribution(row['strategy'] for row in candidates),
                'by_market_regime': _distribution(row['market_regime'] for row in candidates),
                'component_averages': [
                    {'name': name, 'average': round(mean(values), 4), 'coverage': len(values)}
                    for name, values in sorted(component_values.items())
                ],
                'candidates': candidates,
            }

    def mispricing(self, *, limit: int = 3000) -> dict[str, Any]:
        with self.session_factory() as session:
            publication = session.execute(
                select(OptionValuationPublicationModel)
                .where(OptionValuationPublicationModel.publication_name == 'current_option_valuation_intelligence')
                .order_by(desc(OptionValuationPublicationModel.published_at))
            ).scalars().first()
            if not publication:
                return {'status': 'NOT_AVAILABLE', 'summary': {}, 'candidates': []}

            valuation_run_id = (publication.payload_json or {}).get('valuation_run_id')
            query = select(OptionValuationSnapshotModel).order_by(
                desc(OptionValuationSnapshotModel.edge_score),
                desc(OptionValuationSnapshotModel.snapshot_timestamp),
            )
            rows = session.execute(query.limit(max(limit * 4, limit))).scalars().all()
            if valuation_run_id:
                rows = [row for row in rows if (row.payload_json or {}).get('valuation_run_id') == valuation_run_id]
            rows = rows[:limit]
            opportunity_ids = {row.opportunity_id for row in rows}
            recommendation_ids = {row.contract_recommendation_id for row in rows}
            opportunities = session.execute(select(InstitutionalOpportunityModel).where(InstitutionalOpportunityModel.opportunity_id.in_(opportunity_ids))).scalars().all() if opportunity_ids else []
            recommendations = session.execute(select(ContractRecommendationModel).where(ContractRecommendationModel.contract_recommendation_id.in_(recommendation_ids))).scalars().all() if recommendation_ids else []
            strategies = session.execute(select(StrategyCandidateModel).where(StrategyCandidateModel.opportunity_id.in_(opportunity_ids))).scalars().all() if opportunity_ids else []
            valuations = session.execute(select(StrategyValuationModel).where(StrategyValuationModel.opportunity_id.in_(opportunity_ids))).scalars().all() if opportunity_ids else []
            opportunity_map = {row.opportunity_id: row for row in opportunities}
            recommendation_map = {row.contract_recommendation_id: row for row in recommendations}
            selected_strategy = {row.opportunity_id: row for row in strategies if row.selected}
            selected_valuation = {row.opportunity_id: row for row in valuations if row.selected}
            theses = session.execute(select(OpportunityThesisModel).where(OpportunityThesisModel.opportunity_id.in_(opportunity_ids))).scalars().all() if opportunity_ids else []
            thesis_map = {row.opportunity_id: row for row in theses}
            symbols = sorted({row.symbol for row in rows})
            memberships = session.execute(
                select(SectorMembershipModel).where(
                    SectorMembershipModel.symbol.in_(symbols),
                    SectorMembershipModel.is_active.is_(True),
                )
            ).scalars().all() if symbols else []
            membership_by_symbol = {}
            for membership in memberships:
                current = membership_by_symbol.get(membership.symbol)
                if current is None or membership.effective_from > current.effective_from:
                    membership_by_symbol[membership.symbol] = membership

            candidates: list[dict[str, Any]] = []
            driver_values: dict[str, list[float]] = defaultdict(list)
            for row in rows:
                payload = dict(row.payload_json or {})
                opportunity = opportunity_map.get(row.opportunity_id)
                op_payload = dict(opportunity.payload_json or {}) if opportunity else {}
                recommendation = recommendation_map.get(row.contract_recommendation_id)
                rec_payload = dict(recommendation.payload_json or {}) if recommendation else {}
                strategy_row = selected_strategy.get(row.opportunity_id)
                valuation_row = selected_valuation.get(row.opportunity_id)
                thesis = thesis_map.get(row.opportunity_id)
                thesis_payload = dict(thesis.payload_json or {}) if thesis else {}
                membership = membership_by_symbol.get(row.symbol)
                components = _deep(payload, 'components', default={}) or {}
                for name, value in components.items():
                    if isinstance(value, (int, float)):
                        driver_values[str(name)].append(float(value))
                strategy = strategy_row.strategy if strategy_row else _deep(
                    payload, 'segmentation.strategy', default=_deep(rec_payload, 'strategy', 'strategy_name', default='NOT_EVALUATED')
                )
                sector = (membership.sector if membership and membership.sector else None) or _deep(
                    payload, 'segmentation.sector', default=_deep(op_payload, 'sector', 'source_payload.sector', default='NOT_CLASSIFIED')
                )
                regime = _deep(
                    thesis_payload, 'market_regime', 'context.market_regime', default=None
                ) or _deep(op_payload, 'market_regime', 'source_payload.market_regime', 'source_payload.context.market_regime', default='NOT_AVAILABLE')
                dte = _num(_deep(payload, 'dte', 'inputs.dte', default=_deep(rec_payload, 'dte', default=0)))
                moneyness = _deep(payload, 'moneyness_bucket', 'segmentation.moneyness_bucket', 'segmentation.moneyness', default='NOT_AVAILABLE')
                candidates.append({
                    'snapshot_id': row.snapshot_id,
                    'symbol': row.symbol,
                    'opportunity_id': row.opportunity_id,
                    'contract_recommendation_id': row.contract_recommendation_id,
                    'classification': row.classification,
                    'market_mid': float(row.market_mid),
                    'fair_value': float(row.fair_value),
                    'mispricing_pct': float(row.mispricing_pct),
                    'edge_score': float(row.edge_score),
                    'confidence': float(row.confidence),
                    'stability_index': float(row.stability_index),
                    'strategy': str(strategy or 'NOT_EVALUATED'),
                    'sector': str(sector or 'NOT_CLASSIFIED'),
                    'industry': str(membership.industry or '') if membership else '',
                    'company_name': str(membership.company_name or '') if membership else '',
                    'market_regime': str(regime or 'NOT_AVAILABLE'),
                    'opportunity_state': opportunity.state if opportunity else None,
                    'direction': opportunity.direction if opportunity else None,
                    'category': opportunity.category if opportunity else None,
                    'conviction': opportunity.conviction if opportunity else None,
                    'underlying_score': float(opportunity.overall_score) if opportunity else None,
                    'primary_timeframe': thesis.primary_timeframe if thesis else None,
                    'invalidation_level': float(thesis.invalidation_level) if thesis else None,
                    'entry_zone_low': float(thesis.entry_zone_low) if thesis else None,
                    'entry_zone_high': float(thesis.entry_zone_high) if thesis else None,
                    'option_snapshot_id': recommendation.option_snapshot_id if recommendation else None,
                    'dte': dte,
                    'dte_bucket': '0-7' if dte <= 7 else '8-30' if dte <= 30 else '31-60' if dte <= 60 else '61-120' if dte <= 120 else '121+',
                    'moneyness_bucket': str(moneyness or 'UNKNOWN'),
                    'liquidity_score': float(recommendation.liquidity_score or 0.0) if recommendation else 0.0,
                    'executable': bool(recommendation.executable) if recommendation else False,
                    'strategy_score': float(valuation_row.strategy_score) if valuation_row else None,
                    'calibrated_probability': float(valuation_row.calibrated_probability or 0.0) if valuation_row else None,
                    'expected_value': float(valuation_row.expected_value or 0.0) if valuation_row else None,
                    'expected_return_on_risk': float(valuation_row.expected_return_on_risk or 0.0) if valuation_row else None,
                    'components': components,
                    'relative_value': _deep(payload, 'relative_value', default={}),
                    'event_pricing': _deep(payload, 'event_pricing', default={}),
                    'segmentation': _deep(payload, 'segmentation', default={}),
                    'coverage': _deep(payload, 'coverage', default={}),
                    'evidence': _deep(payload, 'evidence', default=[]),
                    'conflicting_evidence': _deep(payload, 'conflicting_evidence', default=[]),
                    'legs': _deep(rec_payload, 'legs', 'contracts', default=[]),
                    'snapshot_timestamp': row.snapshot_timestamp,
                })

            edge_scores = [row['edge_score'] for row in candidates]
            classifications = [row['classification'] for row in candidates]
            summary = {
                'contracts_valued': len(candidates),
                'underpriced': sum('UNDERPRICED' in value for value in classifications),
                'overpriced': sum('OVERPRICED' in value for value in classifications),
                'fair_value': sum(value == 'FAIR_VALUE' for value in classifications),
                'average_edge_score': round(mean(edge_scores), 4) if edge_scores else 0.0,
                'median_edge_score': _percentile(edge_scores, 50),
                'positive_ev': sum((row['expected_value'] or 0) > 0 for row in candidates),
                'executable': sum(row['executable'] for row in candidates),
                'published_at': publication.published_at,
                'publication_id': publication.publication_id,
                'status': publication.status,
            }
            return {
                'status': 'READY',
                'summary': summary,
                'edge_histogram': _histogram(edge_scores),
                'classification_distribution': _distribution(classifications),
                'by_strategy': _distribution(row['strategy'] for row in candidates),
                'by_sector': _distribution(row['sector'] for row in candidates),
                'by_market_regime': _distribution(row['market_regime'] for row in candidates),
                'by_dte': _distribution(row['dte_bucket'] for row in candidates),
                'by_moneyness': _distribution(row['moneyness_bucket'] for row in candidates),
                'driver_averages': [
                    {'name': name, 'average': round(mean(values), 4), 'coverage': len(values)}
                    for name, values in sorted(driver_values.items())
                ],
                'candidates': candidates,
            }
