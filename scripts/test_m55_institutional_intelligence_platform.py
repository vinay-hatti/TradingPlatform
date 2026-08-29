from trading_ai.institutional_intelligence.engines import InstitutionalIntelligenceService
from trading_ai.institutional_intelligence.contracts import IntelligenceCategory

def main():
    opportunity={
      'opportunity_id':'OPP-TEST','snapshot_id':'SNAP-1','snapshot_timestamp':'2026-07-30T14:30:00+00:00','direction':'CALL','strategy':'TREND_FOLLOWING',
      'source_payload':{'spot_price':200,'atr14':4,'ai_score':91,'trend_score':94,'transition_confirmation':82,'dealer_score':78,'institutional_conviction':89,'liquidity_score':92,'risk_score':76,'probability':81,'market_score':84,'delta':.55,'gamma':.03,'theta':-.08,'vega':.12,'contracts':3}
    }
    bundle=InstitutionalIntelligenceService().generate(opportunity)
    assert len(bundle.scores)==9
    assert {s.category for s in bundle.scores}==set(IntelligenceCategory)
    assert bundle.explanation.positive_drivers and bundle.recommendations
    assert bundle.playbook.preferred_strategy=='LONG_CALL'
    assert bundle.playbook.stop < bundle.playbook.entry < bundle.playbook.targets[0]
    assert bundle.health.score>=70
    payload=bundle.to_dict(); assert payload['analytics_version']=='m55.1'
    print('Milestone 55 Institutional Intelligence Platform assertions passed.')
if __name__=='__main__': main()
