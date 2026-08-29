
from trading_ai.autonomous_position_management.policy import load_m73_policy
from trading_ai.autonomous_position_management.service import AutonomousPositionManagementService

def test_version_and_default_governance():
 assert AutonomousPositionManagementService.VERSION.startswith('M74.0.0-')
 assert load_m73_policy().default_automation_mode in {'FULLY_AUTOMATIC','SEMI_AUTOMATIC','ADVISORY'}

def test_priority_contract_present():
 import inspect
 from trading_ai.dynamic_position_management.service import DynamicPositionManagementService
 src=inspect.getsource(DynamicPositionManagementService.evaluate_position)
 assert 'eligible=[]' in src and '[:1]' in src

def test_live_market_override_present():
 import inspect
 from trading_ai.dynamic_position_management.service import DynamicPositionManagementService
 src=inspect.getsource(DynamicPositionManagementService._market_snapshot)
 assert 'POLYGON_DIRECT' in src and 'm73_live_market' in src

def test_structure_zone_trailing_present():
 import inspect
 from trading_ai.dynamic_position_management.service import DynamicPositionManagementService
 assert 'INSTITUTIONAL_STRUCTURE_ZONE' in inspect.getsource(DynamicPositionManagementService._advance_trailing_stop)

def test_production_ui_surfaces_m73():
 from pathlib import Path
 root=Path(__file__).resolve().parents[1]
 text=(root/'ui/workstation/src/pages.tsx').read_text()
 assert 'Autonomous Dynamic Position Management · M73' in text
 assert 'autonomous_management' in text
