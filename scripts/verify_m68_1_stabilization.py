from trading_ai.database.session import SessionLocal
from trading_ai.inflection_intelligence.models import InflectionPublicationModel
from sqlalchemy import select

with SessionLocal() as session:
    publication = session.scalar(select(InflectionPublicationModel).where(InflectionPublicationModel.publication_name == "current_institutional_inflection"))
    if not publication:
        raise SystemExit("publication: FAIL")
    payload = publication.payload_json or {}
    diagnostics = payload.get("diagnostics") or {}
    checks = {
        "publication": publication.status in {"READY", "DEGRADED"},
        "build_mode": payload.get("build_mode") in {"MANUAL", "UNDERLYING_PRIMARY", "OPTIONS_ENRICHMENT"},
        "distribution": all(key in diagnostics for key in ("minimum", "median", "p90", "p95", "maximum", "histogram")),
        "classifications": bool(diagnostics.get("classifications")),
        "transitions": isinstance(diagnostics.get("transition_counts"), dict),
    }
    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    if not all(checks.values()):
        raise SystemExit(1)
    print("Milestone 68.1 stabilization acceptance PASSED")
