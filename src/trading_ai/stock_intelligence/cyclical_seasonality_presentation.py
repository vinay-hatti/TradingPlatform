from __future__ import annotations
import json
from datetime import date, datetime
from pathlib import Path
class CyclicalSeasonalityPresentationService:
    ROOT=Path(__file__).resolve().parents[3]; REPORT_DIR=ROOT/'reports'/'cyclical_seasonality'
    WALK_FORWARD=REPORT_DIR/'cyclical_seasonality_walk_forward_certification.json'; SHADOW_CERT=REPORT_DIR/'cyclical_seasonality_fold_native_shadow_certification.json'; SHADOW_POLICY=REPORT_DIR/'cyclical_seasonality_fold_native_shadow_policy.json'
    @staticmethod
    def _load(p):
        try:return json.loads(p.read_text())
        except (OSError,json.JSONDecodeError):return {}
    @staticmethod
    def _as_date(v):
        if isinstance(v,datetime):return v.date()
        if isinstance(v,date):return v
        try:return date.fromisoformat(str(v or '')[:10])
        except ValueError:return date.today()
    @staticmethod
    def _calendar_states(d):return {'week_of_month':f'W{min(5,((d.day-1)//7)+1)}','month':f'M{d.month:02d}','quarter':f'Q{((d.month-1)//3)+1}'}
    @staticmethod
    def _tone(a,b):
        def f(v):
            u=str(v or '').upper();return 'BULLISH' if 'BULL' in u else 'BEARISH' if 'BEAR' in u else 'NEUTRAL'
        x,y=f(a),f(b)
        return 'NEUTRAL' if 'NEUTRAL' in (x,y) else ('CONFIRMING' if x==y else 'CONFLICTING')
    def build(self,*,symbol,direction,as_of):
        d=self._as_date(as_of); states=self._calendar_states(d); wf=self._load(self.WALK_FORWARD); cert=self._load(self.SHADOW_CERT); policy=self._load(self.SHADOW_POLICY); matches=[]
        for r in wf.get('cohorts') or []:
            factor=r.get('factor')
            if r.get('status')!='WALK_FORWARD_SUPPORTED' or factor not in states or r.get('state')!=states[factor]:continue
            matches.append({'factor_family':r.get('factor_family'),'factor':factor,'state':r.get('state'),'direction':r.get('direction'),'horizon':r.get('horizon'),'alignment':self._tone(direction,r.get('direction')),'full_year_holdouts':r.get('full_year_holdouts'),'full_year_passed':r.get('full_year_passed'),'minimum_passed_holdout_n':r.get('minimum_passed_holdout_n'),'minimum_passed_holdout_thesis_return_pct':r.get('minimum_passed_holdout_thesis_return_pct'),'minimum_passed_holdout_hit_rate_pct':r.get('minimum_passed_holdout_hit_rate_pct'),'status':'WALK_FORWARD_SUPPORTED_NOT_SHADOW_CERTIFIED'})
        matches.sort(key=lambda x:(0 if x['alignment']=='CONFIRMING' else 1 if x['alignment']=='NEUTRAL' else 2,int(x.get('horizon') or 999),str(x.get('factor') or '')))
        confirming=sum(x['alignment']=='CONFIRMING' for x in matches); conflicting=sum(x['alignment']=='CONFLICTING' for x in matches); ws=wf.get('summary') or {}; cs=cert.get('summary') or {}
        alignment='MIXED_RESEARCH_EVIDENCE' if confirming and conflicting else 'CONFIRMING_RESEARCH_EVIDENCE' if confirming else 'CONFLICTING_RESEARCH_EVIDENCE' if conflicting else 'NO_CURRENT_WALK_FORWARD_MATCH'
        return {'version':'M77-CYCLICAL-SEASONALITY-UI-PRESENTATION-1.0','symbol':symbol,'as_of':d.isoformat(),'calendar_state':states,'candidate_direction':direction,'thesis_alignment':alignment,'current_walk_forward_matches':matches,'current_match_count':len(matches),'confirming_match_count':confirming,'conflicting_match_count':conflicting,'research_summary':{'walk_forward_supported':ws.get('walk_forward_supported',0),'supported_20d':ws.get('supported_20d',0),'supported_60d':ws.get('supported_60d',0),'shadow_certified_tier_1':cs.get('shadow_certified_tier_1',0),'shadow_certified_tier_2':cs.get('shadow_certified_tier_2',0),'not_shadow_certified':cs.get('not_shadow_certified',0)},'governance':{'status':'RESEARCH_ONLY_NOT_SHADOW_CERTIFIED','research_only':True,'production_authority_effect':False,'production_score_effect':False,'production_ranking_effect':False,'trade_certification_effect':False,'allocation_effect':False,'execution_effect':False,'automatic_shadow_activation':False,'next_required_gate':policy.get('next_required_gate','LIVE_FORWARD_CYCLICAL_SEASONALITY_SHADOW_CAPTURE_WITH_ZERO_PRODUCTION_EFFECT')}}
