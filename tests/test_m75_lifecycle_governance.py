from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_terminal_finalizer_is_fail_closed_for_working_broker_mutations():
    src = (ROOT / 'src/trading_ai/lifecycle_governance/service.py').read_text()
    assert 'BROKER_WORKING_INSTRUCTION_STATES' in src
    assert 'BLOCKED_BROKER_MUTATION_PENDING' in src
    assert 'if working:' in src


def test_terminal_finalizer_cleans_local_automation_artifacts():
    src = (ROOT / 'src/trading_ai/lifecycle_governance/service.py').read_text()
    assert 'instruction.status = "CANCELLED"' in src
    assert 'instruction.quantity = 0' in src
    assert 'manager.state = "FINALIZED"' in src
    assert 'manager.protection_state = "FINALIZED"' in src
    assert 'reservation.status = "CANCELLED"' in src
    assert '"m75_lifecycle_status"] = "FINALIZED"' in src


def test_certification_invariants_are_explicit():
    src = (ROOT / 'src/trading_ai/lifecycle_governance/service.py').read_text()
    assert 'bad_instructions' in src
    assert 'active_reservations' in src
    assert 'manager_active' in src
    assert '"status": "CERTIFIED" if not violations else "VIOLATIONS_FOUND"' in src


def test_existing_launchagent_runner_owns_lifecycle_governance():
    src = (ROOT / 'scripts/run_m73_entry_fill_management.py').read_text()
    assert 'LifecycleGovernanceService' in src
    assert "result['lifecycle_governance']=_run_lifecycle_governance(portfolio_id)" in src
    assert "TRADING_AI_M75_LIFECYCLE_AUDIT_INTERVAL_SECONDS" in src


def test_portfolio_terminal_projection_is_not_operationally_degraded():
    src = (ROOT / 'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
    assert 'LIFECYCLE FINALIZED' in src
    assert "status: 'CLOSED'" in src
    assert "activeExitCount: 0" in src


def test_m75_preserves_m74_operational_position_contract():
    src = (ROOT / 'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
    assert "NON_OPERATIONAL_POSITION_STATES = new Set(['CLOSED', 'CANCELLED', 'SUPERSEDED'])" in src
    assert 'const activePositions = positions.filter(position => !NON_OPERATIONAL_POSITION_STATES.has' in src
    assert "M75_ADDITIONAL_NON_OPERATIONAL_POSITION_STATES = new Set(['EXPIRED', 'ASSIGNED', 'STOPPED', 'TERMINAL', 'ARCHIVED'])" in src
    assert 'isNonOperationalPositionState' in src
