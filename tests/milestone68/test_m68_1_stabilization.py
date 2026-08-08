from trading_ai.inflection_intelligence.service import InstitutionalInflectionService

def test_diagnostics_distribution_and_classes():
    d=InstitutionalInflectionService._diagnostics([45,55,65,75,85],{'WATCH':2},{'BULLISH':3},{'trend':[50,70]})
    assert d['median']==65
    assert d['classifications']=={'HIGH_CONVICTION':1,'ACTIONABLE':1,'WATCH':1,'DEVELOPING':1,'LOW_SIGNAL':1}
    assert sum(d['histogram'].values())==5

def test_database_engine_has_resilience_controls():
    text=open('src/trading_ai/database/engine.py').read()
    assert 'pool_pre_ping=True' in text and 'pool_recycle=1800' in text

def test_split_ingestion_refreshes_inflection_before_downstream():
    text=open('scripts/ingestion_split_common.py').read()
    assert 'UNDERLYING_PRIMARY' in text
    assert 'OPTIONS_ENRICHMENT' in text
    assert text.index('refresh_inflection_intelligence') < text.index('materialize_institutional_options_opportunities')

def test_production_operations_tracks_inflection():
    text=open('src/trading_ai/production_operations/service.py').read()
    assert 'current_institutional_inflection' in text
    assert "'inflection_intelligence'" in text
