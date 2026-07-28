from pathlib import Path


def test_recovery_script_uses_transport_connection_not_service_connection():
    path = Path("scripts/recover_m50_cancel_ibkr_paper_order.py")
    text = path.read_text()
    assert "transport.connect(config)" in text
    assert "service.connect(" not in text
    assert "IbkrPaperConnectionConfig(" in text
    assert "read_only=False" in text
