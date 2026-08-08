from pathlib import Path
import importlib.util

def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_forecast_resolver_marks_noncanonical_not_eligible(tmp_path):
 p=tmp_path/'u.csv';p.write_text('symbol\nAAPL\nSPY\nQQQ\nIWM\n')
 m=load(Path('src/trading_ai/option_valuation_intelligence/events/forecast_resolver.py'),'fr')
 class S:
  def execute(self,*a,**k):raise AssertionError('database should not be queried')
 v,e=m.GovernedForecastResolver(p).resolve(S(),symbol='ZZZZ',event_date=__import__('datetime').date.today())
 assert v is None and e['eligibility']=='NOT_ELIGIBLE'

def test_fed_parser_uses_historical_year_pages():
 text=Path('scripts/backfill_m69_historical_macro_events.py').read_text()
 assert 'fomchistorical{y}.htm' in text
 assert "Meeting\\s+-\\s+{y}" in text

def test_verifier_is_eligibility_aware():
 text=Path('scripts/verify_m69_event_intelligence_hardening.py').read_text()
 assert 'forecast_eligible' in text and 'forecast_coverage_pct' in text

def test_reconciliation_invalidates_linked_outcomes():
 text=Path('scripts/reconcile_m69_macro_event_integrity.py').read_text()
 assert "status='INVALIDATED'" in text
