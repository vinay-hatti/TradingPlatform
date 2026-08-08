from __future__ import annotations
from statistics import mean
from typing import Iterable
from .profile import *

def _clamp(v,lo=0.,hi=100.): return max(lo,min(hi,float(v)))
def _last_close(profile):
    st=profile.timeframe_states.get(profile.primary_timeframe)
    return float(st.close if st else 0.)
def _atr(profile):
    st=profile.timeframe_states.get(profile.primary_timeframe)
    return max(float(st.atr if st else 0.),0.01)
def _bull(profile): return 'BULLISH' in str(profile.direction)
def _bear(profile): return 'BEARISH' in str(profile.direction)

class DynamicEntryEngine:
    """Build executable entry zones from canonical institutional structure zones."""

    @staticmethod
    def _zone_width(close: float, atr: float, kind: str, structure_width: float | None = None) -> float:
        ratio = {
            EntryType.BREAKOUT.value: 0.20,
            EntryType.RETEST.value: 0.25,
            EntryType.DEMAND_BOUNCE.value: 0.30,
            EntryType.SUPPLY_REJECTION.value: 0.30,
            EntryType.PULLBACK.value: 0.35,
        }.get(kind, 0.30)
        atr_width = max(atr * ratio, atr * 0.10)
        minimum = max(close * 0.0010, 0.01)
        maximum = max(close * 0.0060, minimum)
        if structure_width and structure_width > 0:
            atr_width = min(atr_width, max(minimum, structure_width * 0.60))
        return min(max(atr_width, minimum), maximum)

    def build(self, profile:StockIntelligenceProfile)->EntryProfile:
        close=_last_close(profile);atr=_atr(profile);bull=_bull(profile)
        support_zones=sorted(
            (z for z in profile.structure_zones if z.zone_type=='SUPPORT' and z.representative_price<=close+atr*.25),
            key=lambda z:(abs(close-z.representative_price),-z.strength),
        )
        resistance_zones=sorted(
            (z for z in profile.structure_zones if z.zone_type=='RESISTANCE' and z.representative_price>=close-atr*.25),
            key=lambda z:(abs(close-z.representative_price),-z.strength),
        )
        supports=sorted((x.price for x in profile.support_levels if x.price<=close),reverse=True)
        resistances=sorted(x.price for x in profile.resistance_levels if x.price>=close)
        bstate=getattr(profile.breakout,'state','NONE') if profile.breakout else 'NONE'
        selected_zone=None
        if bull:
            if 'RETEST' in bstate: kind=EntryType.RETEST.value
            elif 'BREAKOUT_CONFIRMED' in bstate or 'BREAKOUT_CONTINUATION' in bstate: kind=EntryType.BREAKOUT.value
            elif support_zones: kind=EntryType.DEMAND_BOUNCE.value
            else: kind=EntryType.PULLBACK.value
            if kind==EntryType.BREAKOUT.value and resistance_zones:
                selected_zone=resistance_zones[0];center=selected_zone.upper_bound;trigger=selected_zone.upper_bound
            else:
                selected_zone=support_zones[0] if support_zones else None
                center=selected_zone.upper_bound if selected_zone else (supports[0] if supports else close)
                trigger=close+.15*atr
        else:
            if 'RETEST' in bstate: kind=EntryType.RETEST.value
            elif 'BREAKDOWN_CONFIRMED' in bstate or 'BREAKDOWN_CONTINUATION' in bstate: kind=EntryType.BREAKOUT.value
            elif resistance_zones: kind=EntryType.SUPPLY_REJECTION.value
            else: kind=EntryType.PULLBACK.value
            if kind==EntryType.BREAKOUT.value and support_zones:
                selected_zone=support_zones[0];center=selected_zone.lower_bound;trigger=selected_zone.lower_bound
            else:
                selected_zone=resistance_zones[0] if resistance_zones else None
                center=selected_zone.lower_bound if selected_zone else (resistances[0] if resistances else close)
                trigger=close-.15*atr
        structure_width=(selected_zone.upper_bound-selected_zone.lower_bound) if selected_zone else None
        full_width=self._zone_width(close,atr,kind,structure_width)
        half_width=full_width/2.0
        low=max(0.01,center-half_width);high=center+half_width
        chase=(high+.35*atr) if bull else max(0.01,low-.35*atr)
        conf=_clamp((profile.confidence+getattr(profile.scores,'confidence',50)+getattr(profile.context,'confidence',50))/3)
        if selected_zone: conf=_clamp(conf*.75+selected_zone.strength*.25)
        distance_atr=abs(close-center)/atr
        fill=_clamp(88-distance_atr*14-(full_width/atr)*8,15,95)
        width_pct=(full_width/close*100) if close else 0.0
        rationale=[f'Primary structure {profile.structure}',f'Direction {profile.direction}']
        if selected_zone:
            rationale.append(
                f'{kind} anchored to {selected_zone.zone_type.lower()} structure zone '
                f'{selected_zone.lower_bound:.2f}-{selected_zone.upper_bound:.2f} '
                f'({", ".join(selected_zone.components)}; {selected_zone.hierarchy}; {selected_zone.status})'
            )
        else:rationale.append(f'{kind} uses legacy nearest structural level fallback')
        rationale.append(f'Entry-zone width capped at {full_width:.2f} ({width_pct:.2f}% of price, {full_width/atr:.2f} ATR)')
        return EntryProfile(kind,round(center,4),round(low,4),round(high,4),round(trigger,4),round(chase,4),round(conf,2),round(fill,2),100.,rationale)

class StructuralStopEngine:
    def build(self, profile:StockIntelligenceProfile, entry:EntryProfile)->StopProfile:
        close=entry.preferred_entry or _last_close(profile);atr=_atr(profile);bull=_bull(profile);c=[]
        def add(t,p,rel,why):
            if p is None or p<=0:return
            dist=abs(close-p)/close*100 if close else 0
            conf=_clamp(rel-(max(0,dist-8)*2),20,95)
            c.append(StopCandidate(t,round(p,4),round(conf,2),round(rel,2),round(dist,2),round(100-conf,2),[why]))
        if bull:
            zones=sorted((z for z in profile.structure_zones if z.zone_type=='SUPPORT' and z.lower_bound<close),key=lambda z:abs(close-z.upper_bound))
            if zones:
                z=zones[0];add('INSTITUTIONAL_STRUCTURE',z.lower_bound-.10*atr,min(95,78+z.confluence_score*.15),f'Below {z.hierarchy.lower().replace("_", " ")} support zone {z.lower_bound:.2f}-{z.upper_bound:.2f}')
            supports=[x for x in profile.support_levels if x.price<close]
            if supports:add('SUPPORT',max(supports,key=lambda x:x.price).price-.15*atr,78,'Below nearest raw support evidence')
            add('ATR',close-1.5*atr,72,'1.5 ATR volatility stop');add('STRUCTURE',close-2.0*atr,76,'Primary-timeframe structural fallback')
        else:
            zones=sorted((z for z in profile.structure_zones if z.zone_type=='RESISTANCE' and z.upper_bound>close),key=lambda z:abs(close-z.lower_bound))
            if zones:
                z=zones[0];add('INSTITUTIONAL_STRUCTURE',z.upper_bound+.10*atr,min(95,78+z.confluence_score*.15),f'Above {z.hierarchy.lower().replace("_", " ")} resistance zone {z.lower_bound:.2f}-{z.upper_bound:.2f}')
            resist=[x for x in profile.resistance_levels if x.price>close]
            if resist:add('RESISTANCE',min(resist,key=lambda x:x.price).price+.15*atr,78,'Above nearest raw resistance evidence')
            add('ATR',close+1.5*atr,72,'1.5 ATR volatility stop');add('STRUCTURE',close+2.0*atr,76,'Primary-timeframe structural fallback')
        selected=max(c,key=lambda x:(x.confidence,-x.distance_pct)) if c else None
        emergency=(close-3*atr if bull else close+3*atr)
        return StopProfile(selected.price if selected else None,selected.stop_type if selected else 'STRUCTURAL',selected.confidence if selected else 0.,c,round(emergency,4),selected.rationale if selected else ['No valid structural stop'])

class DynamicTargetEngine:
    """Rank all directionally valid underlying objectives before selecting T1/T2/T3.

    Primary targets remain the governed management contract consumed downstream.
    Every remaining valid objective is retained as an informational additional target
    with its source/provenance. Wrong-direction/invalid objectives are diagnostics only.
    """

    RANKING_VERSION='M70-TARGET-RANKING-1.0'

    @staticmethod
    def _valid(price:float|None, entry:float, bull:bool)->bool:
        if price is None:
            return False
        price=float(price)
        return price>entry if bull else 0<price<entry

    @staticmethod
    def _hierarchy_bonus(value:str|None)->float:
        return {
            'DEALER_STRUCTURE':10., 'PRIMARY_STRUCTURE':8., 'MAJOR_STRUCTURE':6.,
            'SECONDARY_STRUCTURE':4., 'HISTORICAL_STRUCTURE':2.,
        }.get(str(value or '').upper(),0.)

    def build(self, profile:StockIntelligenceProfile, entry:EntryProfile, stop:StopProfile)->TargetProfile:
        e=entry.preferred_entry or _last_close(profile);atr=_atr(profile);bull=_bull(profile);risk=abs(e-(stop.recommended_stop or e)) or atr
        candidates=[];rejected=[]

        def add(price,source_type,*,components=(),timeframe=None,zone_type=None,hierarchy=None,
                strength=0.,confluence=0.,hold=0.,break_prob=0.,base=50.,rationale=None):
            if price is None:return
            price=float(price)
            rr=abs(price-e)/risk if risk else 0.
            distance=abs(price-e)/e*100 if e else 0.
            item={
                'price':round(price,4),'source_type':str(source_type),'source_components':list(dict.fromkeys(str(x) for x in components if x)),
                'timeframe':timeframe,'zone_type':zone_type,'hierarchy':hierarchy,'strength':round(float(strength or 0),2),
                'confluence_score':round(float(confluence or 0),2),'holding_probability':round(float(hold or 0),4),
                'break_probability':round(float(break_prob or 0),4),'distance_from_entry_pct':round(distance,4),
                'reward_risk':round(rr,4),'selection_status':'CANDIDATE','selection_reason':'GOVERNED_RANKING',
                'rationale':list(rationale or []),
            }
            if not self._valid(price,e,bull):
                item['selection_status']='REJECTED';item['selection_reason']='WRONG_DIRECTION_OR_INVALID_PRICE';rejected.append(item);return
            proximity_penalty=min(rr*1.5,12.)
            score=float(base)+.12*float(strength or 0)+.10*float(confluence or 0)+10.*float(hold or 0)+self._hierarchy_bonus(hierarchy)-proximity_penalty
            item['target_score']=round(_clamp(score),2)
            candidates.append(item)

        # Canonical structural targets.
        if bull:
            for z in profile.structure_zones:
                if z.zone_type=='RESISTANCE':
                    add(z.lower_bound,'INSTITUTIONAL_STRUCTURE',components=getattr(z,'components',()),timeframe=getattr(z,'primary_timeframe',None),zone_type=z.zone_type,hierarchy=getattr(z,'hierarchy',None),strength=getattr(z,'strength',0),confluence=getattr(z,'confluence_score',0),hold=getattr(z,'holding_probability',0),break_prob=getattr(z,'break_probability',0),base=72.,rationale=[f'Resistance structure zone {z.lower_bound:.2f}-{z.upper_bound:.2f}'])
            for x in profile.resistance_levels:
                add(x.price,'RAW_RESISTANCE',components=('PRICE_LEVEL',),timeframe=getattr(x,'timeframe',None),zone_type='RESISTANCE',strength=getattr(x,'strength',0),confluence=getattr(x,'confluence_score',0),hold=getattr(x,'holding_probability',0),break_prob=getattr(x,'break_probability',0),base=58.,rationale=['Raw resistance objective'])
        else:
            for z in profile.structure_zones:
                if z.zone_type=='SUPPORT':
                    add(z.upper_bound,'INSTITUTIONAL_STRUCTURE',components=getattr(z,'components',()),timeframe=getattr(z,'primary_timeframe',None),zone_type=z.zone_type,hierarchy=getattr(z,'hierarchy',None),strength=getattr(z,'strength',0),confluence=getattr(z,'confluence_score',0),hold=getattr(z,'holding_probability',0),break_prob=getattr(z,'break_probability',0),base=72.,rationale=[f'Support structure zone {z.lower_bound:.2f}-{z.upper_bound:.2f}'])
            for x in profile.support_levels:
                add(x.price,'RAW_SUPPORT',components=('PRICE_LEVEL',),timeframe=getattr(x,'timeframe',None),zone_type='SUPPORT',strength=getattr(x,'strength',0),confluence=getattr(x,'confluence_score',0),hold=getattr(x,'holding_probability',0),break_prob=getattr(x,'break_probability',0),base=58.,rationale=['Raw support objective'])

        # Explicit dealer reference prices are useful objectives even when they were
        # merged into a broader structure zone. Their source is retained separately.
        ctx=getattr(profile,'context',None);evidence=getattr(ctx,'evidence',{}) if ctx else {}
        dealer=(evidence or {}).get('dealer_levels',{}) if isinstance(evidence,dict) else {}
        dealer_conf=float(dealer.get('confidence_score') or 0) if isinstance(dealer,dict) else 0.
        if isinstance(dealer,dict):
            for key,label,base in (
                ('gamma_flip','GAMMA_FLIP',70.),('primary_put_wall','PUT_WALL',72.),('primary_call_wall','CALL_WALL',70.)
            ):
                value=dealer.get(key)
                add(value,label,components=(label,),timeframe='DEALER',hierarchy='DEALER_STRUCTURE',strength=dealer_conf,confluence=dealer_conf,hold=.5,base=base,rationale=[f'Dealer {label.lower().replace("_"," ")} objective'])

        # Projection/fallback objectives are now first-class candidates with explicit provenance.
        measured=e+(2*risk if bull else -2*risk)
        expected=e+(2*atr if bull else -2*atr)
        stretch=e+(4*risk if bull else -4*risk)
        sign=1 if bull else -1
        add(measured,'MEASURED_MOVE',components=('RISK_MULTIPLE_2R',),timeframe=profile.primary_timeframe,base=64.,rationale=['Two-risk-unit measured move'])
        add(expected,'EXPECTED_MOVE',components=('ATR_2X',),timeframe=profile.primary_timeframe,base=66.,rationale=['Two-ATR expected move'])
        add(stretch,'STRETCH_TARGET',components=('RISK_MULTIPLE_4R',),timeframe=profile.primary_timeframe,base=52.,rationale=['Four-risk-unit stretch objective'])
        add(e+sign*1.5*risk,'RISK_EXPANSION_1_5R',components=('RISK_FALLBACK',),timeframe=profile.primary_timeframe,base=56.,rationale=['1.5R risk-expansion fallback'])
        add(e+sign*2.5*risk,'RISK_EXPANSION_2_5R',components=('RISK_FALLBACK',),timeframe=profile.primary_timeframe,base=52.,rationale=['2.5R risk-expansion fallback'])
        add(e+sign*4*risk,'RISK_EXPANSION_4R',components=('RISK_FALLBACK',),timeframe=profile.primary_timeframe,base=48.,rationale=['4R risk-expansion fallback'])

        # Merge near-identical objectives while preserving all source evidence.
        directional=sorted(candidates,key=lambda x:x['price'],reverse=not bull)
        merged=[];threshold=.15*atr
        for item in directional:
            match=next((x for x in merged if abs(float(x['price'])-float(item['price']))<=threshold),None)
            if match is None:
                merged.append(dict(item));continue
            sources=list(dict.fromkeys([match['source_type'],item['source_type']]+list(match.get('merged_sources',[]))))
            match['merged_sources']=sources
            match['source_components']=list(dict.fromkeys(list(match.get('source_components',[]))+list(item.get('source_components',[]))))
            match['rationale']=list(dict.fromkeys(list(match.get('rationale',[]))+list(item.get('rationale',[]))))
            if float(item.get('target_score',0))>float(match.get('target_score',0)):
                preserved_sources=match['merged_sources'];preserved_components=match['source_components'];preserved_rationale=match['rationale']
                match.update(item);match['merged_sources']=preserved_sources;match['source_components']=preserved_components;match['rationale']=preserved_rationale
            match['selection_reason']='MERGED_CONFLUENCE'

        # Rank on evidence quality, then assign T1/T2/T3 by actual price encounter sequence.
        ranked=sorted(merged,key=lambda x:(-float(x.get('target_score',0)),float(x.get('reward_risk',0))))
        selected=ranked[:3]
        selected_ids={id(x) for x in selected}
        selected=sorted(selected,key=lambda x:x['price'],reverse=not bull)
        levels=[]
        for i,item in enumerate(selected):
            rr=float(item['reward_risk']);score=float(item.get('target_score',50))
            prob=_clamp(58.+score*.28-rr*3.0,20,90)
            item['selection_status']='PRIMARY';item['selection_reason']='TOP_THREE_GOVERNED_SCORE'
            source=item['source_type'];components=', '.join(item.get('source_components',[]))
            why=f'{source}' + (f' ({components})' if components else '')
            levels.append(TargetLevel(f'TARGET_{i+1}',round(float(item['price']),4),round(prob,2),round(rr,2),[why]+list(item.get('rationale',[]))))

        additional=[]
        for item in sorted((x for x in ranked if id(x) not in selected_ids),key=lambda x:x['price'],reverse=not bull):
            value=dict(item);value['selection_status']='ADDITIONAL';value['selection_reason']='VALID_OBJECTIVE_NOT_PRIMARY_TOP_THREE';additional.append(value)

        return TargetProfile(
            levels,round(measured,4),round(expected,4),round(stretch,4),
            ['Primary targets are the top three governed objectives and are ordered by execution sequence; remaining valid objectives are retained as additional targets.'],
            additional,rejected,self.RANKING_VERSION,
        )
class TrailingIntelligenceEngine:
    def build(self, profile:StockIntelligenceProfile, entry:EntryProfile, stop:StopProfile, targets:TargetProfile)->TrailingProfile:
        e=entry.preferred_entry or _last_close(profile);method='INSTITUTIONAL_STRUCTURE'
        if profile.structure=='EXPANSION':method='ATR'
        elif profile.structure in {'TRENDING','EARLY_TREND','MATURE_TREND'}:method='SWING_STRUCTURE'
        activation=targets.targets[0].price if targets.targets else e
        trail=stop.recommended_stop
        return TrailingProfile(method,activation,trail,0.75 if method=='ATR' else 0.,round(_clamp(profile.confidence*.9+10),2),[f'{method} trail selected from structure {profile.structure}', 'Activate after first structural objective'])

class UnderlyingExitEngine:
    def evaluate(self, original:StockIntelligenceProfile, current:StockIntelligenceProfile|None=None)->ExitIntelligence:
        current=current or original
        base=100.;reasons=[];warnings=[]
        if original.direction!=current.direction:
            base-=42;reasons.append('Primary direction changed')
        base-=max(0,original.alignment_score-current.alignment_score)*.35
        if current.structure in {'EXHAUSTION','REVERSAL_ATTEMPT'}:base-=18;reasons.append(f'Current structure {current.structure}')
        if current.participation and current.participation.deterioration_risk>65:base-=16;reasons.append('Institutional deterioration risk elevated')
        if current.context and current.context.adjustment<-4:base-=12;reasons.append('External context opposes thesis')
        if current.breakout and current.breakout.failure_probability>65:base-=18;reasons.append('Breakout/breakdown failure risk elevated')
        health=_clamp(base);decay='STABLE';action=ExitAction.HOLD.value;reason=ExitReason.THESIS_HEALTHY.value;reduce=0.
        if health<35:action=ExitAction.EXIT.value;reason=ExitReason.UNDERLYING_STRUCTURE_INVALIDATED.value;decay='INVALIDATED'
        elif health<55:action=ExitAction.REDUCE.value;reason=ExitReason.TREND_DETERIORATION.value;decay='DETERIORATING';reduce=.5
        elif health<75:action=ExitAction.TRAIL.value;reason=ExitReason.MOMENTUM_REVERSAL.value;decay='WEAKENING'
        elif health>92 and current.scores and current.scores.overall>85:action=ExitAction.SCALE_IN.value;decay='STRENGTHENING'
        return ExitIntelligence(action,reason,round(health,2),round(health,2),decay,reduce,action==ExitAction.SCALE_IN.value,warnings,reasons or ['Underlying thesis remains intact'])

class PositionIntelligenceEngine:
    def __init__(self):self.entry=DynamicEntryEngine();self.stop=StructuralStopEngine();self.targets=DynamicTargetEngine();self.trailing=TrailingIntelligenceEngine();self.exit=UnderlyingExitEngine()
    def build(self, profile:StockIntelligenceProfile, current_profile:StockIntelligenceProfile|None=None)->PositionIntelligenceProfile:
        e=self.entry.build(profile);s=self.stop.build(profile,e);t=self.targets.build(profile,e,s);tr=self.trailing.build(profile,e,s,t);x=self.exit.evaluate(profile,current_profile)
        rr=max((z.reward_risk for z in t.targets),default=0.)
        quality=_clamp(mean([e.confidence,s.confidence,tr.confidence,x.thesis_integrity,getattr(profile.scores,'confidence',50)]))
        dte=10 if profile.primary_timeframe in {'5m','15m','30m','1h'} else 30
        return PositionIntelligenceProfile(e,s,t,tr,x,dte,round(rr,2),round(quality,2)).finalize()
