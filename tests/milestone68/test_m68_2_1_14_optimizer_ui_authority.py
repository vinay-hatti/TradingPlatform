from __future__ import annotations

from pathlib import Path

import pytest

from trading_ai.portfolio_risk_allocation.config import (
    MAX_NEW_POSITIONS_ENV,
    MAX_NEW_POSITIONS_MAX,
    MAX_NEW_POSITIONS_MIN,
    load_portfolio_optimizer_config,
)
from trading_ai.portfolio_risk_allocation.optimizer import (
    PortfolioOptimizationService,
)


def test_dotenv_position_cap_accepts_100_and_rejects_outside_range(
    tmp_path: Path,
):
    env_file = tmp_path / ".env"
    env_file.write_text(f"{MAX_NEW_POSITIONS_ENV}=100\n", encoding="utf-8")
    assert MAX_NEW_POSITIONS_MIN == 1
    assert MAX_NEW_POSITIONS_MAX == 100
    assert load_portfolio_optimizer_config(env_file).max_new_positions == 100

    for invalid in (0, 101):
        env_file.write_text(
            f"{MAX_NEW_POSITIONS_ENV}={invalid}\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="between 1 and 100"):
            load_portfolio_optimizer_config(env_file)


def test_controlled_optimizer_override_uses_same_100_position_limit():
    assert PortfolioOptimizationService.resolved_policy(
        {"max_new_positions": 100}
    )["max_new_positions"] == 100
    with pytest.raises(ValueError, match="between 1 and 100"):
        PortfolioOptimizationService.resolved_policy(
            {"max_new_positions": 101}
        )


def test_institutional_options_ui_projects_exact_optimizer_authority():
    root = Path(__file__).resolve().parents[2]
    page = (
        root / "ui/workstation/src/InstitutionalOptionsPage.tsx"
    ).read_text(encoding="utf-8")

    assert "function tradeBuilderAuthority" in page
    assert "optimizer.optimality_proven===true" in page
    assert "optimizer.selected===true" in page
    assert "optimizer.status==='SELECTED_GLOBAL_FEASIBLE'" in page
    assert "optimizer.selected===false" in page
    assert "optimizer.status==='NOT_SELECTED_GLOBAL_FEASIBLE'" in page
    assert "const handoffReady=tradeBuilder.authorized" in page
    assert "disabled={!handoffReady||!!busy}" in page
    assert "Review the decision and open it in Trade Builder." not in page


def test_ui_explains_selected_unselected_and_stale_optimizer_states():
    root = Path(__file__).resolve().parents[2]
    page = (
        root / "ui/workstation/src/InstitutionalOptionsPage.tsx"
    ).read_text(encoding="utf-8")

    assert (
        "Globally selected and authorized for Trade Builder review." in page
    )
    assert (
        "Executable, but not selected in the current globally optimal "
        "portfolio. No Trade Builder handoff is authorized."
    ) in page
    assert (
        "Current optimizer-selection authority is unavailable or stale. "
        "Rebuild portfolio authority."
    ) in page
    assert "Global portfolio selection" in page


def test_ui_preserves_conditional_entry_governance_from_current_source():
    root = Path(__file__).resolve().parents[2]
    page = (
        root / "ui/workstation/src/InstitutionalOptionsPage.tsx"
    ).read_text(encoding="utf-8")

    assert "ENTRY_NOT_READY" in page
    assert "finalCert.execution_disposition" in page
    assert "finalCert.entry_execution?.reason_codes" in page
    assert "Governed plan is waiting for its entry" in page
    assert 'label="Entry disposition"' in page
    assert (
        "Entry execution and global portfolio selection are governed "
        "separately."
    ) in page
