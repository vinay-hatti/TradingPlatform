from .profile import *
class StockContextIntegrationService:
    def integrate(self,direction,trend=None,institutional=None,dealer=None,market_regime=None,forecast=None,breadth=None,sector=None):
        bullish='BULL' in str(direction); vals=[]; evidence={}; warnings=[]
        def add(name,val,weight=1): vals.append((val,weight));evidence[name]=val
        td=str(getattr(trend,'short_term_trend',getattr(trend,'direction','UNKNOWN')) if trend else 'UNKNOWN').upper(); add('trend',80 if ('BULL' in td)==bullish and td!='UNKNOWN' else 20 if td!='UNKNOWN' else 50,1.4)
        mr=str(getattr(market_regime,'regime',getattr(market_regime,'current_regime','UNKNOWN')) if market_regime else 'UNKNOWN').upper(); add('market_regime',75 if ('BULL' in mr)==bullish and mr!='UNKNOWN' else 25 if mr!='UNKNOWN' else 50,1.2)
        fd=str(getattr(forecast,'direction',getattr(forecast,'forecast_direction','UNKNOWN')) if forecast else 'UNKNOWN').upper(); add('forecast',72 if ('BULL' in fd)==bullish and fd!='UNKNOWN' else 28 if fd!='UNKNOWN' else 50,1)
        rs=float(getattr(trend,'relative_strength_vs_spy',0) if trend else 0); add('relative_strength',max(0,min(100,50+(rs if bullish else -rs)*5)),1)
        dl=str(getattr(dealer,'positioning_label','UNKNOWN') if dealer else 'UNKNOWN').upper(); add('dealer',70 if ('BULL' in dl)==bullish and dl!='UNKNOWN' else 45 if dl in ('NEUTRAL','UNKNOWN') else 30,1)
        evidence['dealer_levels']={
            'gamma_flip':getattr(dealer,'gamma_flip',None) if dealer else None,
            'primary_call_wall':getattr(dealer,'primary_call_wall',None) if dealer else None,
            'primary_put_wall':getattr(dealer,'primary_put_wall',None) if dealer else None,
            'confidence_score':float(getattr(dealer,'confidence_score',0) or 0) if dealer else 0.0,
        }
        ps=float(getattr(institutional,'participation_score',50) if institutional else 50); add('institutional',ps if bullish else 100-ps,1)
        if not trend:warnings.append('trend context unavailable')
        score=sum(v*w for v,w in vals)/sum(w for _,w in vals); adj=max(-12,min(12,(score-50)*.24)); conf=max(20,100-len(warnings)*15)
        return StockContextProfile(round(score,2),round(adj,2),conf,mr,fd,str(getattr(trend,'relative_strength_grade','') if trend else ''),dl,str(getattr(dealer,'gamma_regime','UNKNOWN') if dealer else 'UNKNOWN'),str(getattr(institutional,'participation_state','UNKNOWN') if institutional else 'UNKNOWN'),evidence|{'warnings':warnings})
