from trading_ai.database.base import Base
from trading_ai.database import models  # noqa: F401

EXPECTED = {
    "canonical_orders", "canonical_order_events", "paper_executions", "paper_fills",
    "portfolio_cash_reservations", "paper_trading_sessions", "paper_automation_checkpoints",
    "paper_trading_controls", "paper_position_marks", "paper_position_lifecycle_events",
}
missing = EXPECTED - set(Base.metadata.tables)
assert not missing, f"Missing Milestone 49 metadata tables: {sorted(missing)}"
print("Milestone 49 migration and metadata contract assertions passed.")
