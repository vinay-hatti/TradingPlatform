from pathlib import Path

root = Path(__file__).resolve().parents[1]
required = [
    root / "src/trading_ai/opportunity_domain/profile.py",
    root / "src/trading_ai/opportunity_domain/models.py",
    root / "src/trading_ai/opportunity_domain/repository.py",
    root / "src/trading_ai/opportunity_domain/service.py",
    root / "src/trading_ai/opportunity_domain/policy.py",
    root / "migrations/versions/m54_001_canonical_opportunity_domain.py",
]
for path in required:
    assert path.exists(), path
profile = (root / "src/trading_ai/opportunity_domain/profile.py").read_text()
for state in ("STAGED", "UNDER_REVIEW", "APPROVED", "REJECTED", "TRADE_BUILT", "PAPER_SUBMITTED", "ARCHIVED"):
    assert state in profile
service = (root / "src/trading_ai/opportunity_domain/service.py").read_text()
assert "expected_version" in service
assert "snapshot_id" in service and "scanner_run_id" in service
print("Milestone 54 Phase 1 canonical Opportunity domain assertions passed.")
