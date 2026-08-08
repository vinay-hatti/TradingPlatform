from trading_ai.futures_intelligence.service import PRODUCT_INDEX, PolygonFuturesProvider, FuturesIntelligenceService
from trading_ai.futures_intelligence.models import FuturesContractModel,FuturesBarModel,FuturesIntelligenceSnapshotModel
from trading_ai.opex_intelligence.service import OpexIntelligenceService

def main():
    assert PRODUCT_INDEX=={'ES':'SPX','NQ':'NDX','RTY':'RUT'}
    assert PolygonFuturesProvider.__name__
    assert FuturesIntelligenceService.VERSION.startswith('M71.2')
    assert OpexIntelligenceService.VERSION.startswith('M71.'), OpexIntelligenceService.VERSION
    for model in (FuturesContractModel,FuturesBarModel,FuturesIntelligenceSnapshotModel):assert model.__tablename__
    print('M71.2 Futures/OPEX acceptance: PASS')
if __name__=='__main__':main()
