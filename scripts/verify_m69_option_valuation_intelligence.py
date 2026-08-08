from collections import Counter
from math import isfinite

from sqlalchemy import select

from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.models import (
    OptionValuationPublicationModel,
    OptionValuationSnapshotModel,
)

with SessionLocal() as s:
    publication = s.execute(
        select(OptionValuationPublicationModel).where(
            OptionValuationPublicationModel.publication_name == 'current_option_valuation_intelligence'
        )
    ).scalars().first()
    publication_payload = dict(publication.payload_json or {}) if publication else {}
    run_id = publication_payload.get('valuation_run_id')
    all_rows = s.execute(select(OptionValuationSnapshotModel)).scalars().all()
    rows = [r for r in all_rows if (r.payload_json or {}).get('valuation_run_id') == run_id] if run_id else []
    payloads = [dict(r.payload_json or {}) for r in rows]
    classes = Counter(r.classification for r in rows)
    diagnostics = dict(publication_payload.get('diagnostics') or {})

    independent = [p for p in payloads if p.get('valuation_basis') == 'INDEPENDENT_MODEL']
    materially_independent = [
        p for p in independent
        if abs(float(p.get('model_fair_value', 0)) - float(p.get('market_mid', 0))) > 1e-6
    ]
    required_coverage = ('volatility', 'realized_volatility', 'forecast_volatility', 'dealer_flow', 'liquidity')
    coverage_ok = all(
        bool(p.get('component_coverage'))
        and 'component_coverage_pct' in p
        and all(name in p['component_coverage'] for name in required_coverage)
        for p in payloads
    )
    coverage_pct = float(diagnostics.get('average_component_coverage_pct') or 0)
    execution_p95 = float((diagnostics.get('execution_penalty_pct') or {}).get('p95') or 0)
    mispricing = diagnostics.get('mispricing_pct') or {}
    distribution_span = float(mispricing.get('p95') or 0) - float(mispricing.get('p05') or 0)

    checks = {
        'publication': bool(publication and run_id),
        'snapshots': len(rows) > 0,
        'independent_fair_value': bool(independent) and len(independent) == len(rows) and len(materially_independent) >= max(1, int(len(rows) * 0.05)),
        'five_band_classification': all(r.classification in {
            'STRONG_UNDERPRICED', 'MODERATELY_UNDERPRICED', 'FAIR_VALUE',
            'MODERATELY_OVERPRICED', 'STRONG_OVERPRICED'
        } for r in rows),
        'edge_attribution': all(len(p.get('components') or {}) >= 8 for p in payloads),
        'component_coverage': coverage_ok and coverage_pct >= 45,
        'diagnostics': bool(mispricing) and bool(diagnostics.get('histogram')) and bool(diagnostics.get('coverage_counts')),
        'robust_normalization': all(float(p.get('reference_value', 0)) >= 0.25 for p in payloads) and distribution_span >= 1.0,
        'execution_friction': execution_p95 <= 8.01,
        'stability': all(0 <= r.stability_index <= 100 and isfinite(r.stability_index) for r in rows),
        'relative_value_domain': int(diagnostics.get('relative_value_available_count') or 0) > 0 and all('relative_value' in p for p in payloads),
        'event_domain': all('event_pricing' in p for p in payloads) and 'event_available_count' in diagnostics,
        'segmented_diagnostics': all(k in (diagnostics.get('segmented') or {}) for k in ('sector','strategy','dte_bucket','moneyness','liquidity_bucket')),
    }
    for key, value in checks.items():
        print(f'{key}: {"PASS" if value else "FAIL"}')
    if not all(checks.values()):
        raise SystemExit('Milestone 69.4 analytical acceptance FAILED')
    print(f'Current valuation run: {run_id}')
    print(f'Valuation snapshots: {len(rows)}')
    print('Classifications:', dict(classes))
    print('Mispricing diagnostics:', mispricing)
    print('Average component coverage:', coverage_pct)
    print('Execution penalty p95:', execution_p95)
    print('Milestone 69.4 analytical acceptance PASSED')
