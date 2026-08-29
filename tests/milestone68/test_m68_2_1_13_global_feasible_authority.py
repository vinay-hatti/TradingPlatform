from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from itertools import combinations

import pytest

from trading_ai.portfolio_risk_allocation.config import (
    MAX_NEW_POSITIONS_ENV,
    load_portfolio_optimizer_config,
)
from trading_ai.portfolio_risk_allocation.optimizer import (
    PortfolioOptimizationService,
)


def _decision(opportunity_id: str, symbol: str, score: float, capital: float):
    return SimpleNamespace(
        opportunity_id=opportunity_id,
        final_portfolio_score=score,
        decision="ACCEPT",
        rank=int(opportunity_id[-1]),
        payload_json={
            "decision_identity": {"opportunity_id": opportunity_id},
            "symbol": symbol,
            "sector": "TEST_SECTOR",
            "strategy": "LONG_CALL",
            "scores": {
                "final_portfolio_score": score,
                "portfolio_fit_score": score,
                "opportunity_cost_score": score,
            },
            "capital_allocation": {
                "recommended_quantity": 1,
                "recommended_capital": capital,
            },
            "portfolio_impact": {
                "marginal_heat_pct": 0.1,
                "marginal_var_95": 10.0,
                "marginal_greeks": {},
            },
            "correlation": {"portfolio_correlation": 0.1},
        },
    )


def test_max_new_positions_is_strictly_loaded_from_dotenv(tmp_path: Path):
    env_file = tmp_path / ".env"
    with pytest.raises(ValueError, match=MAX_NEW_POSITIONS_ENV):
        load_portfolio_optimizer_config(env_file)
    env_file.write_text(f"{MAX_NEW_POSITIONS_ENV}=7\n", encoding="utf-8")
    loaded = load_portfolio_optimizer_config(env_file)
    assert loaded.max_new_positions == 7
    assert str(env_file) in loaded.source


def test_exact_solver_beats_order_dependent_greedy_allocation():
    service = object.__new__(PortfolioOptimizationService)
    policy = PortfolioOptimizationService.resolved_policy({
        "max_new_positions": 2,
        "max_new_capital_pct": 5.0,
        "max_single_candidate_capital_pct": 10.0,
        "max_portfolio_heat_pct": 20.0,
        "max_symbol_pct": 20.0,
        "max_sector_pct": 100.0,
        "max_strategy_pct": 100.0,
        "max_pair_correlation": 0.80,
        "min_final_portfolio_score": 62.0,
        "max_candidates_considered": 1000,
        "exact_solver_node_limit": 100_000,
    })
    risk = {
        "net_liquidation": 100_000.0,
        "portfolio_heat_pct": 0.0,
        "payload_json": {
            "exposures": {"symbol": {}, "sector": {}, "strategy": {}}
        },
    }
    budgets = {
        "portfolio": {"new_capital_remaining": 5_000.0},
    }
    # Greedy chooses A (100 points, all capital).  The exact optimum is B+C
    # (140 points), proving selection is not an input-order artifact.
    selected, rejected, proof = service._select_candidates(
        [
            _decision("OPP1", "A", 100.0, 5_000.0),
            _decision("OPP2", "B", 70.0, 2_500.0),
            _decision("OPP3", "C", 70.0, 2_500.0),
        ],
        risk,
        budgets,
        policy,
    )
    assert {item["symbol"] for item in selected} == {"B", "C"}
    assert proof["optimality_proven"] is True
    assert proof["objective_total_score"] == 140.0
    skipped_a = next(item for item in rejected if item["symbol"] == "A")
    assert "NOT_IN_GLOBAL_OPTIMAL_SUBSET" in skipped_a["rejection_reasons"]


def test_exact_solver_matches_exhaustive_subset_enumeration():
    service = object.__new__(PortfolioOptimizationService)
    policy = PortfolioOptimizationService.resolved_policy({
        "max_new_positions": 3,
        "max_new_capital_pct": 5.0,
        "max_single_candidate_capital_pct": 10.0,
        "max_portfolio_heat_pct": 20.0,
        "max_symbol_pct": 20.0,
        "max_sector_pct": 100.0,
        "max_strategy_pct": 100.0,
        "max_pair_correlation": 0.80,
        "min_final_portfolio_score": 62.0,
        "max_candidates_considered": 1000,
        "exact_solver_node_limit": 100_000,
    })
    risk = {
        "net_liquidation": 100_000.0,
        "portfolio_heat_pct": 0.0,
        "payload_json": {
            "exposures": {"symbol": {}, "sector": {}, "strategy": {}}
        },
    }
    budgets = {"portfolio": {"new_capital_remaining": 5_000.0}}
    specifications = [
        ("A", 97.0, 4_500.0),
        ("B", 83.0, 2_500.0),
        ("C", 79.0, 2_000.0),
        ("D", 72.0, 1_500.0),
        ("E", 68.0, 1_000.0),
        ("F", 64.0, 900.0),
    ]
    decisions = [
        _decision(f"OPP{index}", symbol, score, capital)
        for index, (symbol, score, capital) in enumerate(
            specifications, 1
        )
    ]
    selected, _, proof = service._select_candidates(
        decisions, risk, budgets, policy
    )
    enumerated = [
        (
            sum(item[1] for item in subset),
            {item[0] for item in subset},
        )
        for size in range(4)
        for subset in combinations(specifications, size)
        if sum(item[2] for item in subset) <= 5_000.0
    ]
    brute_force = max(
        enumerated,
        key=lambda item: item[0],
    )
    assert proof["objective_total_score"] == brute_force[0]
    assert {item["symbol"] for item in selected} == brute_force[1]


def test_source_contains_exhaustive_package_and_handoff_governance():
    root = Path(__file__).resolve().parents[2]
    contract_source = (
        root / "src/trading_ai/institutional_options/contract_optimization.py"
    ).read_text(encoding="utf-8")
    handoff_source = (
        root / "src/trading_ai/institutional_options/handoff.py"
    ).read_text(encoding="utf-8")
    assert "all_eligible_strategies_evaluated" in contract_source
    assert "EXHAUSTIVE_EXECUTABLE_PACKAGE_AUTHORITY" in contract_source
    assert "alternative_executable_count" not in contract_source
    assert "SELECTED_GLOBAL_FEASIBLE" in handoff_source
