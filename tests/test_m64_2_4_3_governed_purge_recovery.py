from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_ai.portfolio_risk_allocation.history_governance import (
    M64DecisionHistoryPurgeService,
)


def test_purge_requires_explicit_confirmation_before_opening_database_session():
    opened = False

    def factory():
        nonlocal opened
        opened = True
        raise AssertionError("database session must not open")

    service = M64DecisionHistoryPurgeService(factory)
    with pytest.raises(PermissionError):
        service.purge_known_invalid_history(
            "PAPER-PRIMARY",
            target_risk_snapshot_id="M64-RISK-PINNED",
            confirmation_token="wrong-token",
        )
    with pytest.raises(ValueError, match="requires a pinned risk snapshot"):
        service.purge_known_invalid_history(
            "PAPER-PRIMARY",
            target_risk_snapshot_id=None,
            confirmation_token=service.CONFIRMATION_TOKEN,
        )
    assert opened is False


def test_purge_refuses_non_postgresql_database():
    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    service = M64DecisionHistoryPurgeService(FakeSession)
    with pytest.raises(RuntimeError, match="requires PostgreSQL"):
        service.purge_known_invalid_history(
            "PAPER-PRIMARY",
            target_risk_snapshot_id="M64-RISK-PINNED",
            confirmation_token=service.CONFIRMATION_TOKEN,
        )


def test_purge_source_has_fail_closed_protection_and_no_cascade():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "src/trading_ai/portfolio_risk_allocation/history_governance.py"
    ).read_text()

    for token in (
        "OTHER_PORTFOLIO",
        "PUBLISHED_RISK",
        "PINNED_RECOVERY_RISK",
        "DIRECT_REFERENCE:",
        "OPERATIONAL_OPPORTUNITY_LATEST:",
        "FORENSIC_BOUNDARY_SAMPLE:",
        "target_risk_validation",
        "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS",
        "FROM pg_constraint",
        "TRUNCATE TABLE {source}",
        "INSERT INTO {source}",
        "Current publication changed during governed purge",
    ):
        assert token in source
    assert "TRUNCATE TABLE {source} CASCADE" not in source


def test_authority_no_longer_waits_for_legacy_per_row_cleanup():
    root = Path(__file__).resolve().parents[1]
    orchestration = (
        root / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text()

    assert "compact_non_authoritative_history" not in orchestration
    assert (
        orchestration.index("risk_snapshot_lookup_started")
        < orchestration.rindex("purge_known_invalid_history")
        < orchestration.index("decision_generation_started")
    )
    assert "prune_expired_history" in orchestration
    assert '"status": "DEFERRED_NON_BLOCKING"' in orchestration


def test_operator_requires_purge_flag_and_writes_durable_manifest():
    root = Path(__file__).resolve().parents[1]
    operator = (
        root / "scripts/run_m64_2_1_regenerate_current_portfolio_decisions.py"
    ).read_text()
    wrapper = (
        root / "scripts/run_m64_2_4_3_governed_purge_and_regenerate.py"
    ).read_text()
    preflight = (
        root / "scripts/run_m64_2_4_3_purge_preflight.py"
    ).read_text()

    assert "--confirm-purge-known-invalid-history" in operator
    assert "--purge-manifest-output" in operator
    assert "os.fsync" in operator
    assert "os.replace" in operator
    assert "main(require_governed_purge=True)" in wrapper
    assert "dry_run=True" in preflight
    assert "_write_json_atomic" in preflight
