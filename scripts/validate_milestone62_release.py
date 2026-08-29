from pathlib import Path
from trading_ai.database.base import Base
import trading_ai.institutional_options.models  # noqa: F401

required_tables = {
    "institutional_option_opportunities",
    "institutional_option_theses",
    "institutional_option_strategy_candidates",
    "institutional_option_strategy_comparisons",
    "institutional_option_contract_recommendations",
    "institutional_option_execution_recommendations",
    "institutional_option_outcome_attributions",
    "institutional_option_opportunity_audit",
    "institutional_option_strategy_valuations",
    "institutional_option_management_snapshots",
    "institutional_option_handoffs",
    "institutional_option_outcome_observations",
    "institutional_option_learning_snapshots",
}
missing = required_tables - set(Base.metadata.tables)
if missing:
    raise SystemExit(f"Missing Milestone 62 tables: {sorted(missing)}")
router = Path("src/trading_ai/institutional_options/router.py").read_text()
page = Path("ui/workstation/src/InstitutionalOptionsPage.tsx").read_text()
app = Path("ui/workstation/src/App.tsx").read_text()
pages = Path("ui/workstation/src/pages.tsx").read_text()
for token in ("/workspace/opportunities", "/contracts/optimize", "/strategies/value", "/management/generate", "/handoff/trade-builder", "/outcomes/capture", "/learning/summarize"):
    if token not in router:
        raise SystemExit(f"Missing API token: {token}")
for token in ("institutional-options", "Institutional options"):
    if token not in app + pages + page:
        raise SystemExit(f"Missing UI token: {token}")
print("Milestone 62 release validation passed.")
print(f"Registered tables: {len(required_tables)}")
