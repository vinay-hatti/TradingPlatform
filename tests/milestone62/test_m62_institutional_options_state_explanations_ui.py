from pathlib import Path


def test_institutional_options_state_explanations_and_rejection_reasons():
    root = Path(__file__).resolve().parents[2]
    page = (root / "ui/workstation/src/InstitutionalOptionsPage.tsx").read_text()
    styles = (root / "ui/workstation/src/styles.css").read_text()

    for state in (
        "DISCOVERED",
        "VALIDATED",
        "STRATEGIES_GENERATED",
        "CONTRACTS_OPTIMIZED",
        "READY_FOR_EXECUTION",
        "EXECUTED",
        "ACTIVE",
        "CLOSED",
        "ATTRIBUTED",
        "REJECTED",
        "CANCELLED",
    ):
        assert state in page

    assert "Next governed action" in page
    assert "Why this opportunity was rejected" in page
    assert "eligibility_warnings" in page
    assert "new_state==='REJECTED'" in page
    assert "rejection_reasons" in page
    assert "Pipeline progress" in page
    assert "Executable contracts" in page
    assert "io-workflow-progress" in page
    assert ".io-rejection-panel" in styles
    assert ".io-progress-track" in styles
