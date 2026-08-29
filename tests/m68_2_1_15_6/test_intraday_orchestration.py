from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_underlying_precedes_options_and_lineage_gate():
    s=(ROOT/'scripts/m69_6_scheduled/run_intraday.sh').read_text()
    assert s.index('scripts/ingest_underlying_data.py') < s.index('--capture-current-stock-run') < s.index('scripts/ingest_options_data.py') < s.index('--expected-stock-run-id')
    assert 'LOCK_NAME="m69_6_market_pipeline"' in s
    assert 'set -euo pipefail' in s
def test_m66_daemon_is_simulation_unless_execute_explicit():
    s=(ROOT/'scripts/run_m66_production_operations.py').read_text()
    assert "once(not a.execute)" in s
    assert "p.add_argument('--execute',action='store_true')" in s
