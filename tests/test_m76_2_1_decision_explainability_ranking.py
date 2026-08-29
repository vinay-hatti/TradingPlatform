from pathlib import Path

from trading_ai.stock_intelligence.decision_intelligence import InstitutionalDecisionAssessment, InstitutionalDecisionIntelligenceEngine
from trading_ai.stock_intelligence.profile import StockIntelligenceProfile


def test_rank_population_persists_operator_friendly_rank_label_and_top_percent():
    engine = InstitutionalDecisionIntelligenceEngine()
    profiles = []
    for symbol, capital, quality, readiness in [('AAA', 90, 88, 85), ('BBB', 80, 82, 80), ('CCC', 70, 75, 74)]:
        p = StockIntelligenceProfile(symbol=symbol, snapshot_timestamp='2026-08-14T14:00:00+00:00')
        p.decision_intelligence = InstitutionalDecisionAssessment(
            capital_priority=capital,
            overall_trade_quality=quality,
            decision_readiness=readiness,
        ).finalize()
        profiles.append(p)
    ranked = engine.rank_population(profiles)
    first = ranked[0].decision_intelligence.competition
    last = ranked[-1].decision_intelligence.competition
    assert first['rank_label'] == 'Rank #1 / 3'
    assert first['top_percent'] == 33.33
    assert last['rank_label'] == 'Rank #3 / 3'
    assert last['top_percent'] == 100.0


def test_explainability_is_part_of_persisted_assessment_contract():
    a = InstitutionalDecisionAssessment(explainability={
        'version': 'M76.2.1-EXPLAINABILITY-1.0',
        'trade_quality': {'components': []},
        'decision_readiness': {'components': {}},
        'capital_priority': {'components': {}},
    }).finalize()
    assert a.explainability['version'] == 'M76.2.1-EXPLAINABILITY-1.0'
    assert a.state_hash


def test_stock_scanner_surfaces_rank_and_decision_decomposition():
    root = Path(__file__).resolve().parents[1]
    src = (root / 'ui/workstation/src/StockIntelligenceScannerPage.tsx').read_text()
    assert 'Rank #${marketRank} / ${populationSize}' in src
    assert 'Trade quality breakdown' in src
    assert 'Decision readiness breakdown' in src
    assert 'Capital priority breakdown' in src
    assert 'P(Target 3 before stop)' in src
    assert 'Freshness & barrier diagnostics' in src


def test_institutional_options_inherits_rank_and_explainability():
    root = Path(__file__).resolve().parents[1]
    src = (root / 'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    assert 'Rank #${idiRank} / ${idiPopulation}' in src
    assert 'Decision intelligence explainability' in src
    assert 'Trade quality breakdown' in src
    assert 'Decision readiness breakdown' in src
    assert 'Capital priority breakdown' in src
    assert 'Target 3 before stop' in src
