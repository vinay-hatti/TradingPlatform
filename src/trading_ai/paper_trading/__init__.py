"""Paper-trading automation foundation."""

from .paper_trading_policy import PaperTradingAutomationPolicy
from .paper_trading_profile import (
    PaperTradingCheck,
    PaperTradingCycleProfile,
    PaperTradingRuntimeState,
    PaperTradingSessionDecision,
    PaperTradingSessionProfile,
)
from .paper_trading_runtime_repository import (
    JsonPaperTradingRuntimeRepository,
)
from .paper_trading_session_engine import PaperTradingSessionEngine
from .paper_trading_session_service import PaperTradingSessionService
from .paper_trading_state_machine import PaperTradingSessionStateMachine

__all__ = [
    "JsonPaperTradingRuntimeRepository",
    "PaperTradingAutomationPolicy",
    "PaperTradingCheck",
    "PaperTradingCycleProfile",
    "PaperTradingRuntimeState",
    "PaperTradingSessionDecision",
    "PaperTradingSessionEngine",
    "PaperTradingSessionProfile",
    "PaperTradingSessionService",
    "PaperTradingSessionStateMachine",
]
"""Optional exports for Milestone 30 Phase 6 Step 2."""
from .paper_decision_adapter import PaperDecisionPipelineAdapter
from .paper_scan_cycle_service import PaperScanCycleService
from .paper_scan_engine import PaperScanEngine
from .paper_scan_policy import PaperScanAutomationPolicy
from .paper_scan_profile import (
    PaperDecisionPipelineResult,
    PaperOrderDraft,
    PaperScanCandidate,
    PaperScanCycleResult,
)
from .paper_signal_order_mapper import PaperSignalOrderMapper
"""Optional exports for Milestone 30 Phase 6 Step 3."""
from .paper_commission_model import PaperCommissionModel
from .paper_execution_engine import PaperExecutionEngine
from .paper_execution_policy import PaperExecutionPolicy
from .paper_execution_profile import (
    PaperExecutionCheck,
    PaperExecutionDecision,
    PaperExecutionRecord,
    PaperExecutionRequest,
    PaperFillProfile,
    PaperMarketQuote,
)
from .paper_execution_repository import JsonPaperExecutionRepository
from .paper_execution_service import PaperExecutionService
from .paper_fill_simulator import PaperFillSimulator
from .paper_latency_model import PaperLatencyModel
from .paper_slippage_model import PaperSlippageModel
"""Optional exports for Milestone 30 Phase 6 Step 4."""
from .paper_adjustment_engine import PaperAdjustmentEngine
from .paper_position_engine import PaperPositionEngine
from .paper_position_policy import PaperPositionPolicy
from .paper_position_profile import (
    PaperAdjustmentProposal,
    PaperExitSignal,
    PaperPositionDecision,
    PaperPositionLot,
    PaperPositionProfile,
)
from .paper_position_repository import JsonPaperPositionRepository
from .paper_position_service import PaperPositionService
from .paper_automation_orchestrator import PaperAutomationOrchestrator
from .paper_automation_repository import JsonPaperAutomationRepository
from .paper_automation_profile import PaperAutomationCheckpoint, PaperAutomationCycleResult
from .paper_trading_reporting import PaperTradingOperationalReport
