from datetime import date
from trading_ai.stock_intelligence.cyclical_seasonality_presentation import CyclicalSeasonalityPresentationService as S
def test_calendar(): assert S._calendar_states(date(2026,8,21))=={'week_of_month':'W3','month':'M08','quarter':'Q3'}
def test_alignment(): assert S._tone('BULLISH','STRONG_BULLISH')=='CONFIRMING' and S._tone('BULLISH','BEARISH')=='CONFLICTING'
