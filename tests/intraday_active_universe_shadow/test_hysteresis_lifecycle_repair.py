from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_intraday_active_universe_shadow.py"


def _load_hysteresis_namespace(history: Path):
    tree = ast.parse(SCRIPT.read_text())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if "DIRECT_POLICY_QUALIFIER_REASONS" in names:
                keep.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {"normalize_symbol", "hysteresis"}:
            keep.append(node)
    ns = {"json": json, "HISTORY": history}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(SCRIPT), "exec"), ns)
    return ns


def _row(date: str, reasons: dict[str, list[str]]):
    return {
        "mode": "SHADOW_INTRADAY_DECISION",
        "market_session": True,
        "market_date": date,
        "proposed_active_symbols": sorted(reasons),
        "inclusion_reasons": reasons,
    }


def _write_history(path: Path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_policy_thresholds_remain_frozen():
    text = SCRIPT.read_text()
    assert 'VERSION="INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.3.2"' in text
    assert "score>=70" in text
    assert "score>=60" in text
    assert "len(evidence)>=2" in text
    assert '"production_effect":False' in text


def test_cross_session_membership_does_not_seed_hysteresis(tmp_path):
    history = tmp_path / "history.jsonl"
    _write_history(history, [_row("2026-08-27", {"AAA": ["STOCK_INTELLIGENCE_HIGH_SCORE"]})])
    ns = _load_hysteresis_namespace(history)
    assert ns["hysteresis"]("2026-08-28") == set()


def test_direct_qualification_seeds_same_session_hysteresis(tmp_path):
    history = tmp_path / "history.jsonl"
    _write_history(history, [_row("2026-08-28", {"AAA": ["STOCK_INTELLIGENCE_HIGH_SCORE"]})])
    ns = _load_hysteresis_namespace(history)
    assert ns["hysteresis"]("2026-08-28") == {"AAA"}


def test_hysteresis_only_membership_cannot_self_renew(tmp_path):
    history = tmp_path / "history.jsonl"
    t0 = _row("2026-08-28", {"AAA": ["STOCK_INTELLIGENCE_HIGH_SCORE"]})
    t1 = _row("2026-08-28", {"AAA": ["ELIGIBILITY_HYSTERESIS"]})
    _write_history(history, [t0, t1])
    ns = _load_hysteresis_namespace(history)
    # T2 may still retain AAA because T0 is one of the last two observations.
    assert ns["hysteresis"]("2026-08-28") == {"AAA"}
    t2 = _row("2026-08-28", {"AAA": ["ELIGIBILITY_HYSTERESIS"]})
    _write_history(history, [t0, t1, t2])
    ns = _load_hysteresis_namespace(history)
    # T3 must drop AAA: the last two observations contain no direct qualifier.
    assert ns["hysteresis"]("2026-08-28") == set()


def test_non_policy_reasons_do_not_seed_hysteresis(tmp_path):
    history = tmp_path / "history.jsonl"
    _write_history(history, [
        _row("2026-08-28", {"AAA": ["MANDATORY_CORE_ETF_REFERENCE"]}),
        _row("2026-08-28", {"BBB": ["OPEN_POSITION"]}),
    ])
    ns = _load_hysteresis_namespace(history)
    assert ns["hysteresis"]("2026-08-28") == set()


def test_all_three_direct_policy_routes_seed_hysteresis(tmp_path):
    history = tmp_path / "history.jsonl"
    _write_history(history, [
        _row("2026-08-28", {
            "AAA": ["STOCK_INTELLIGENCE_HIGH_SCORE"],
            "BBB": ["STOCK_INTELLIGENCE_DISCOVERY_COMBINATION"],
            "CCC": ["MULTI_DOMAIN_DISCOVERY_COMBINATION"],
        })
    ])
    ns = _load_hysteresis_namespace(history)
    assert ns["hysteresis"]("2026-08-28") == {"AAA", "BBB", "CCC"}


def test_shadow_script_compiles():
    import py_compile
    py_compile.compile(str(SCRIPT), doraise=True)
