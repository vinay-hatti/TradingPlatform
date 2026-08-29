from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_m62_handoff_propagates_selected_strategy_into_trade_builder_economics():
    src = (ROOT / 'src/trading_ai/institutional_options/handoff.py').read_text()
    assert 'AdvancedTradeBuilderService.economics(tuple(legs), float(capital), float(risk_budget_pct), strategy.strategy)' in src


def test_execution_intelligence_recomputes_economics_with_trade_plan_strategy():
    src = (ROOT / 'src/trading_ai/execution_intelligence/service.py').read_text()
    assert 'AdvancedTradeBuilderService.economics(trade_legs,float(tp.capital),float(tp.risk_budget_pct),tp.strategy)' in src
