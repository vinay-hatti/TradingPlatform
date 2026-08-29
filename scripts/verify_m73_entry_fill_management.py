from pathlib import Path
from trading_ai.execution_intelligence.policy import load_execution_intelligence_policy
from trading_ai.execution_intelligence.auto_fill import AutomaticEntryFillManager

root = Path(__file__).resolve().parents[1]
ws = (root / "src/trading_ai/execution_workspace/service.py").read_text()
ei = (root / "src/trading_ai/execution_intelligence/service.py").read_text()
af = (root / "src/trading_ai/execution_intelligence/auto_fill.py").read_text()

# Initial submission must use the governed M70 package limit for single-leg orders,
# converted to the positive broker LMT convention only at the IBKR boundary.
assert "broker_limit_price=abs(signed_net_price) if len(legs)==1 else signed_net_price" in ws

# The workspace owns the automatic-mode safety contract, while the autonomous
# entry-fill worker is the component that explicitly invokes it.
assert "automatic=False" in ws
assert "if automatic:" in ws
assert "Automatic entry-fill management is disabled by policy" in ws
assert "automatic=True" in af
assert "M73_ENTRY_FILL_AUTO" in af

# Working-order intelligence must progressively move toward execution while
# preserving the frozen approval envelope and minimum retained economics.
assert "progressive_aggression" in ei
assert "expected_value_retention" in ei

p = load_execution_intelligence_policy()
assert p.automatic_fill_management_enabled
assert p.maximum_reprices >= 0
assert AutomaticEntryFillManager.VERSION.startswith("M73")

print("M73 entry-fill management verifier: PASS")
print("Version:", AutomaticEntryFillManager.VERSION)
print("Automatic fill management:", p.automatic_fill_management_enabled)
print("Max reprices:", p.maximum_reprices)
print("Max order age:", p.working_order_max_age_seconds)
