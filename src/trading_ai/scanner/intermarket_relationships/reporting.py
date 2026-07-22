def render_console_report(run_profile) -> str:
    return "\n".join(
        [
            "=" * 72,
            "Milestone 35 Phase 5 Step 2 — Intermarket Relationships",
            "=" * 72,
            f"As-of date          : {run_profile.as_of_date}",
            f"Records read        : {run_profile.records_read}",
            f"Symbols available   : {run_profile.symbols_available}",
            f"Symbols missing     : {run_profile.symbols_missing}",
            f"Market state        : {run_profile.market_state}",
            f"Confidence          : {run_profile.confidence:.6f}",
            f"Governance          : {run_profile.governance_status}",
            f"Output              : {run_profile.output_path}",
        ]
    )
