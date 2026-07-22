from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence
from uuid import uuid4

def utc_now()->datetime: return datetime.now(timezone.utc)
class ScannerStatus(str,Enum):
    IDLE="IDLE"; INITIALIZING="INITIALIZING"; SCANNING="SCANNING"; PAUSED="PAUSED"; COMPLETED="COMPLETED"; FAILED="FAILED"
class DashboardView(str,Enum):
    HOME="HOME"; SCANNER="SCANNER"; RANKINGS="RANKINGS"; CANDIDATE="CANDIDATE"; SETTINGS="SETTINGS"; REPORTS="REPORTS"
class DashboardEventType(str,Enum):
    SESSION_CREATED="SESSION_CREATED"; UNIVERSE_LOADED="UNIVERSE_LOADED"; SCANNER_STARTED="SCANNER_STARTED"; SCANNER_PAUSED="SCANNER_PAUSED"; SCANNER_RESUMED="SCANNER_RESUMED"; RANKING_UPDATED="RANKING_UPDATED"; CANDIDATE_OPENED="CANDIDATE_OPENED"; SETTINGS_CHANGED="SETTINGS_CHANGED"; SCAN_COMPLETED="SCAN_COMPLETED"; SCAN_FAILED="SCAN_FAILED"; NAVIGATION_CHANGED="NAVIGATION_CHANGED"; PROGRESS_UPDATED="PROGRESS_UPDATED"
@dataclass(frozen=True)
class DashboardConfiguration:
    top_n:int=50; refresh_interval_seconds:int=5; autosave:bool=True; persist_events:bool=True; default_view:DashboardView=DashboardView.HOME; metadata:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class ScannerProgress:
    universe_size:int=0; symbols_completed:int=0; symbols_failed:int=0; symbols_skipped:int=0; symbols_per_second:float=0.0; elapsed_seconds:float=0.0; eta_seconds:float|None=None
    @property
    def symbols_remaining(self)->int:
        return max(0,self.universe_size-self.symbols_completed-self.symbols_failed-self.symbols_skipped)
    @property
    def completion_pct(self)->float:
        if self.universe_size<=0:return 0.0
        return min(100.0,max(0.0,(self.universe_size-self.symbols_remaining)/self.universe_size*100.0))
@dataclass(frozen=True)
class RankingRecord:
    symbol:str; rank:int; institutional_score:float; probability_score:float; expected_move:float|None=None; regime:str|None=None; sector:str|None=None; exchange:str|None=None; optionable:bool|None=None; is_etf:bool|None=None; cross_asset_score:float|None=None; metadata:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class DashboardNavigationState:
    current_view:DashboardView=DashboardView.HOME; previous_view:DashboardView|None=None; selected_symbol:str|None=None; breadcrumbs:Sequence[str]=field(default_factory=tuple)
@dataclass(frozen=True)
class DashboardEvent:
    event_type:DashboardEventType; occurred_at:datetime=field(default_factory=utc_now); payload:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class ScannerSession:
    session_id:str=field(default_factory=lambda:uuid4().hex); status:ScannerStatus=ScannerStatus.IDLE; created_at:datetime=field(default_factory=utc_now); started_at:datetime|None=None; completed_at:datetime|None=None; failed_at:datetime|None=None; failure_reason:str|None=None; universe_name:str|None=None; last_refresh_at:datetime=field(default_factory=utc_now)
@dataclass(frozen=True)
class DashboardSnapshot:
    schema_version:str; generated_at:datetime; configuration:DashboardConfiguration; session:ScannerSession; navigation:DashboardNavigationState; progress:ScannerProgress; rankings:Sequence[RankingRecord]; events:Sequence[DashboardEvent]
    def to_dict(self)->dict[str,Any]: return asdict(self)
