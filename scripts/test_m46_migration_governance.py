from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "scripts" / "run_migration_governance_audit.py"

spec = importlib.util.spec_from_file_location("migration_governance_audit", AUDIT_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

records = module.load_revisions()
errors = module.audit_graph(records)
errors += module.audit_postgres_identifiers()
errors += module.audit_m46_literal_widths()
assert not errors, "\n".join(errors)
assert any(record.revision == "m46_002" and record.down_revisions == ("m46_001",) for record in records)
assert all(len(record.revision) <= module.ALEMBIC_VERSION_LIMIT for record in records)
print("Milestone 46 migration governance assertions passed.")
