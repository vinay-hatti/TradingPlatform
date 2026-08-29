from pathlib import Path
import json

from trading_ai.research.m77.capacity_aware_capital_allocation_shadow import (
    BINDING_VERSION,
    CapacityAwareShadowConfig,
    _protocol_payload,
    status,
)


def main() -> int:
    root = Path('/Users/vinay.hatti/TradingPlatform')
    module = root / 'src/trading_ai/research/m77/capacity_aware_capital_allocation_shadow.py'
    text = module.read_text()
    checks = {
        'binding_version': BINDING_VERSION == 'M77.40.1-GOVERNED-PRODUCTION-CAPACITY-AUTHORITY-CPRE-LIVE-INPUT-BINDING-1.0',
        'protocol_version_unchanged': _protocol_payload()['version'] == 'M77.40.0-FROZEN-PROSPECTIVE-CAPACITY-AWARE-CAPITAL-ALLOCATION-SHADOW-1.0',
        'protocol_id_unchanged': _protocol_payload()['protocol_id'] == 'CACA-CANDIDATE-001',
        'sessionlocal_reader': 'from trading_ai.database.session import SessionLocal' in text,
        'current_portfolio_allocation_reader': 'current_portfolio_allocation' in text,
        'cpre_protocol_gate': 'CPRE-CANDIDATE-001' in text,
        'market_date_gate': 'Portfolio allocation market-date mismatch' in text,
        'no_production_effect': _protocol_payload()['production_capital_allocation_effect'] is False,
    }
    failed = [k for k, v in checks.items() if not v]
    print(json.dumps({'checks': checks, 'failed': failed}, indent=2, sort_keys=True))
    if failed:
        return 2
    print(json.dumps(status(CapacityAwareShadowConfig(project_root=str(root))), indent=2, sort_keys=True))
    print('M77.40.1 verification PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
