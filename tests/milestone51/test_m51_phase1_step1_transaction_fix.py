from pathlib import Path

from trading_ai.paper_trading.automated_order_handoff import service as handoff_service


def test_canonical_persistence_uses_existing_session_transaction():
    source = Path(handoff_service.__file__).read_text(encoding="utf-8")
    method = source.split("    def _ensure_canonical", 1)[1]
    assert "with session.begin()" not in method
    assert "session.commit()" in method
    assert "session.rollback()" in method
