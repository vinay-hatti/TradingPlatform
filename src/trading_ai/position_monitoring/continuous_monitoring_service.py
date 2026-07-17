from __future__ import annotations
from .continuous_monitoring_orchestrator import ContinuousMonitoringOrchestrator
class ContinuousMonitoringService:
    def __init__(self,orchestrator: ContinuousMonitoringOrchestrator)->None:self.orchestrator=orchestrator
    def run_once(self,**kwargs):return self.orchestrator.run_cycle(**kwargs)
