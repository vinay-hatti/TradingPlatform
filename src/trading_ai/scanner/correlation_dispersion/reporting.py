def render_console_report(run_profile) -> str:
    return "\n".join(
        [
            "=" * 72,
            "Milestone 35 Phase 5 Step 4 — Correlation & Dispersion",
            "=" * 72,
            f"As-of date          : {run_profile.as_of_date}",
            f"Records read        : {run_profile.records_read}",
            f"Symbols available   : {run_profile.symbols_available}",
            f"Pair count          : {run_profile.pair_count}",
            f"Correlation regime  : {run_profile.correlation_regime}",
            f"Dispersion regime   : {run_profile.dispersion_regime}",
            f"Market structure    : {run_profile.market_structure_state}",
            f"Confidence          : {run_profile.confidence:.6f}",
            f"Governance          : {run_profile.governance_status}",
            f"Output              : {run_profile.output_path}",
        ]
    )
