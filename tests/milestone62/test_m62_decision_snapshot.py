from pathlib import Path

from trading_ai.database.base import Base
from trading_ai.institutional_options.decision import InstitutionalDecisionPolicy
from trading_ai.institutional_options.models import InstitutionalDecisionSnapshotModel


def test_decision_snapshot_table_registered():
    assert InstitutionalDecisionSnapshotModel.__tablename__ in Base.metadata.tables
    columns = Base.metadata.tables[InstitutionalDecisionSnapshotModel.__tablename__].columns
    for name in ("decision_snapshot_id", "opportunity_id", "strategy_candidate_id", "contract_recommendation_id", "state_hash", "payload_json"):
        assert name in columns


def test_decision_policy_is_versioned_and_governed():
    policy = InstitutionalDecisionPolicy()
    assert policy.policy_version == "M62-DECISION-1.0"
    assert 0 < policy.minimum_institutional_score <= 100


def test_decision_api_and_migration_are_present():
    root = Path(__file__).resolve().parents[2]
    router = (root / "src/trading_ai/institutional_options/router.py").read_text()
    migration = (root / "migrations/versions/m62_005_institutional_decision_snapshots.py").read_text()
    ui = (root / "ui/workstation/src/InstitutionalOptionsPage.tsx").read_text()
    assert '/decisions/build' in router
    assert '/opportunities/{opportunity_id}/decision' in router
    assert 'down_revision = "m62_004"' in migration
    assert 'Build decision snapshot' in ui
