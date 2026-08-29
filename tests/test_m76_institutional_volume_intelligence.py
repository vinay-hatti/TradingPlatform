from trading_ai.stock_intelligence.volume_intelligence import InstitutionalVolumeIntelligenceEngine


def _bars(*, bullish=True, spike=True, n=80):
    rows=[]
    price=100.0
    for i in range(n):
        drift=(0.16 if bullish else -0.16)
        open_=price
        close=max(5.0, price+drift)
        high=max(open_,close)+0.55
        low=min(open_,close)-0.45
        vol=1_000_000*(1.0 + (i%5)*0.02)
        if i >= n-7:
            vol*=1.35
        if spike and i == n-1:
            vol*=2.2
            close += 1.5 if bullish else -1.5
            high=max(high,close+0.3);low=min(low,close-0.3)
        rows.append({'open':open_,'high':high,'low':low,'close':close,'volume':vol})
        price=close
    return rows


def test_bullish_breakout_volume_is_detected():
    result=InstitutionalVolumeIntelligenceEngine().analyze(_bars(bullish=True),breakout_state='BREAKOUT_CONFIRMED',structure='MATURE_TREND')
    assert result.relative_volume_1d > 2
    assert result.breakout_confirmation_score >= 70
    assert result.signal == 'BREAKOUT_EXPANSION'
    assert result.institutional_participation_score > 60


def test_bearish_breakdown_volume_is_detected():
    result=InstitutionalVolumeIntelligenceEngine().analyze(_bars(bullish=False),breakout_state='BREAKDOWN_CONFIRMED',structure='MATURE_TREND')
    assert result.relative_volume_1d > 2
    assert result.breakdown_confirmation_score >= 70
    assert result.signal == 'BREAKDOWN_EXPANSION'
    assert result.distribution_score > result.accumulation_score


def test_volume_profile_exposes_persistence_and_relative_volume():
    result=InstitutionalVolumeIntelligenceEngine().analyze(_bars(bullish=True,spike=False),structure='COMPRESSION')
    assert result.relative_volume_5d > 1
    assert result.persistence_score > 0
    assert 'elevated_volume_sessions_10d' in result.evidence


def test_stock_scanner_projection_contains_institutional_volume_fields():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/'src/trading_ai/stock_intelligence/publication.py').read_text()
    for marker in ('institutional_volume_score','institutional_volume_regime','institutional_volume_signal','relative_volume_1d'):
        assert marker in src


def test_stock_scanner_ui_surfaces_and_filters_volume_signal():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/'ui/workstation/src/StockIntelligenceScannerPage.tsx').read_text()
    assert '<th>Volume</th>' in src
    assert "headerSelect('volume', options.volume)" in src
    assert 'Institutional volume' in src
    assert 'Volume persistence' in src


def test_institutional_options_carries_volume_evidence():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/'src/trading_ai/institutional_options/opportunity_ingestion.py').read_text()
    assert 'Institutional volume:' in src
    assert '"institutional_volume": volume' in src
