# Milestone 47 — Published-State Consumption: Complete

Milestone 47 is complete through Phase 8.

- Phase 1 — Published-State Resolver
- Phase 2 — Daily Scanner Consumption
- Phase 3 — Institutional Decision Consumption
- Phase 4 — Staleness and Failure Governance
- Phase 5 — Persistent Lineage
- Phase 6 — Reporting Integration
- Phase 7 — Historical Replay
- Phase 8 — End-to-End Validation and Certification

The production chain is now:

```text
market_ingestion_publication
        ↓
PublishedMarketStateResolver
        ↓
Daily Scanner
        ↓
Scanner and Candidate Lineage
        ↓
Institutional Decision Engine
        ↓
Decision Lineage
        ↓
Auditable Reports and Manifests
        ↓
Historical Replay
        ↓
End-to-End Certification
```

Release certification is performed with `scripts/run_m47_end_to_end_certification.py`.
