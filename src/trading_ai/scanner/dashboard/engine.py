from __future__ import annotations
from dataclasses import replace
from datetime import datetime,timezone
from typing import Iterable,Sequence
from .contracts import DashboardConfiguration,DashboardEvent,DashboardEventType,DashboardNavigationState,DashboardSnapshot,DashboardView,RankingRecord,ScannerProgress,ScannerSession,ScannerStatus
from .policy import ScannerDashboardPolicy

def _now(): return datetime.now(timezone.utc)
class ScannerDashboardEngine:
    def __init__(self,policy:ScannerDashboardPolicy|None=None): self.policy=policy or ScannerDashboardPolicy()
    def create_snapshot(self,configuration:DashboardConfiguration|None=None)->DashboardSnapshot:
        c=configuration or DashboardConfiguration(); self.policy.validate_configuration(c); s=ScannerSession(); n=DashboardNavigationState(current_view=c.default_view)
        return DashboardSnapshot(self.policy.schema_version,_now(),c,s,n,ScannerProgress(),tuple(),(DashboardEvent(DashboardEventType.SESSION_CREATED,payload={"session_id":s.session_id}),))
    def initialize_universe(self,snapshot:DashboardSnapshot,*,universe_name:str,universe_size:int)->DashboardSnapshot:
        self.policy.validate_transition(snapshot.session.status,ScannerStatus.INITIALIZING); now=_now()
        return self._event(snapshot,session=replace(snapshot.session,status=ScannerStatus.INITIALIZING,universe_name=universe_name,last_refresh_at=now),progress=replace(snapshot.progress,universe_size=max(0,universe_size)),event=DashboardEvent(DashboardEventType.UNIVERSE_LOADED,payload={"universe_name":universe_name,"universe_size":universe_size}))
    def start_scan(self,snapshot:DashboardSnapshot)->DashboardSnapshot:
        self.policy.validate_transition(snapshot.session.status,ScannerStatus.SCANNING); now=_now(); et=DashboardEventType.SCANNER_RESUMED if snapshot.session.status is ScannerStatus.PAUSED else DashboardEventType.SCANNER_STARTED
        return self._event(snapshot,session=replace(snapshot.session,status=ScannerStatus.SCANNING,started_at=snapshot.session.started_at or now,last_refresh_at=now),event=DashboardEvent(et))
    def pause_scan(self,snapshot:DashboardSnapshot)->DashboardSnapshot:
        self.policy.validate_transition(snapshot.session.status,ScannerStatus.PAUSED)
        return self._event(snapshot,session=replace(snapshot.session,status=ScannerStatus.PAUSED,last_refresh_at=_now()),event=DashboardEvent(DashboardEventType.SCANNER_PAUSED))
    def update_progress(self,snapshot:DashboardSnapshot,*,symbols_completed:int,symbols_failed:int=0,symbols_skipped:int=0,elapsed_seconds:float=0.0)->DashboardSnapshot:
        processed=symbols_completed+symbols_failed+symbols_skipped; rate=processed/elapsed_seconds if elapsed_seconds>0 else 0.0; remaining=max(0,snapshot.progress.universe_size-processed)
        p=ScannerProgress(snapshot.progress.universe_size,max(0,symbols_completed),max(0,symbols_failed),max(0,symbols_skipped),rate,max(0.0,elapsed_seconds),remaining/rate if rate>0 else None)
        return replace(snapshot,generated_at=_now(),session=replace(snapshot.session,last_refresh_at=_now()),progress=p)
    def update_rankings(self,snapshot:DashboardSnapshot,rankings:Iterable[RankingRecord])->DashboardSnapshot:
        ordered=sorted(rankings,key=lambda r:(r.rank,-r.institutional_score,-r.probability_score)); limited=tuple(ordered[:min(snapshot.configuration.top_n,self.policy.max_rankings)])
        return self._event(snapshot,rankings=limited,event=DashboardEvent(DashboardEventType.RANKING_UPDATED,payload={"ranking_count":len(limited)}))
    def navigate(self,snapshot:DashboardSnapshot,view:DashboardView,selected_symbol:str|None=None)->DashboardSnapshot:
        self.policy.validate_navigation(view); n=DashboardNavigationState(view,snapshot.navigation.current_view,selected_symbol,self._breadcrumbs(view,selected_symbol)); et=DashboardEventType.CANDIDATE_OPENED if view is DashboardView.CANDIDATE and selected_symbol else DashboardEventType.NAVIGATION_CHANGED
        return self._event(snapshot,navigation=n,event=DashboardEvent(et,payload={"view":view.value,"selected_symbol":selected_symbol}))
    def complete_scan(self,snapshot:DashboardSnapshot)->DashboardSnapshot:
        self.policy.validate_transition(snapshot.session.status,ScannerStatus.COMPLETED); now=_now()
        return self._event(snapshot,session=replace(snapshot.session,status=ScannerStatus.COMPLETED,completed_at=now,last_refresh_at=now),event=DashboardEvent(DashboardEventType.SCAN_COMPLETED))
    def fail_scan(self,snapshot:DashboardSnapshot,reason:str)->DashboardSnapshot:
        self.policy.validate_transition(snapshot.session.status,ScannerStatus.FAILED); now=_now()
        return self._event(snapshot,session=replace(snapshot.session,status=ScannerStatus.FAILED,failed_at=now,failure_reason=reason,last_refresh_at=now),event=DashboardEvent(DashboardEventType.SCAN_FAILED,payload={"reason":reason}))
    def _event(self,snapshot:DashboardSnapshot,*,event:DashboardEvent,session:ScannerSession|None=None,navigation:DashboardNavigationState|None=None,progress:ScannerProgress|None=None,rankings:Sequence[RankingRecord]|None=None)->DashboardSnapshot:
        events=tuple(snapshot.events)+(event,) if snapshot.configuration.persist_events else (event,)
        return replace(snapshot,generated_at=_now(),session=session or snapshot.session,navigation=navigation or snapshot.navigation,progress=progress or snapshot.progress,rankings=rankings if rankings is not None else snapshot.rankings,events=events)
    @staticmethod
    def _breadcrumbs(view,selected):
        if view is DashboardView.CANDIDATE and selected:return ("HOME","SCANNER","RANKINGS",selected.upper())
        if view is DashboardView.RANKINGS:return ("HOME","SCANNER","RANKINGS")
        if view is DashboardView.SCANNER:return ("HOME","SCANNER")
        return ("HOME",view.value) if view is not DashboardView.HOME else ("HOME",)
