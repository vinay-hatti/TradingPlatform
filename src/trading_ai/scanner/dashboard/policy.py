from __future__ import annotations
from dataclasses import dataclass
from .contracts import DashboardConfiguration, DashboardView, ScannerStatus
@dataclass(frozen=True)
class ScannerDashboardPolicy:
    schema_version:str="m35.phase5.step1.v1"; max_rankings:int=100; min_refresh_interval_seconds:int=1; max_refresh_interval_seconds:int=300
    def validate_configuration(self,c:DashboardConfiguration)->None:
        if c.top_n not in {10,25,50,100}: raise ValueError("top_n must be one of: 10, 25, 50, 100")
        if not self.min_refresh_interval_seconds<=c.refresh_interval_seconds<=self.max_refresh_interval_seconds: raise ValueError("refresh_interval_seconds outside permitted dashboard range")
    def validate_transition(self,current:ScannerStatus,target:ScannerStatus)->None:
        allowed={ScannerStatus.IDLE:{ScannerStatus.INITIALIZING,ScannerStatus.FAILED},ScannerStatus.INITIALIZING:{ScannerStatus.SCANNING,ScannerStatus.FAILED},ScannerStatus.SCANNING:{ScannerStatus.PAUSED,ScannerStatus.COMPLETED,ScannerStatus.FAILED},ScannerStatus.PAUSED:{ScannerStatus.SCANNING,ScannerStatus.FAILED},ScannerStatus.COMPLETED:set(),ScannerStatus.FAILED:set()}
        if target not in allowed[current]: raise ValueError(f"invalid scanner transition: {current.value} -> {target.value}")
    def validate_navigation(self,view:DashboardView)->None:
        if not isinstance(view,DashboardView): raise ValueError("unknown dashboard view")
