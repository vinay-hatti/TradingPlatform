def render_console_report(run_profile) -> str:
    return "\n".join(
        [
            "=" * 72,
            "Milestone 35 Phase 5 Step 3 — Sector Leadership & Rotation",
            "=" * 72,
            f"As-of date          : {run_profile.as_of_date}",
            f"Records read        : {run_profile.records_read}",
            f"Sectors available   : {run_profile.sectors_available}",
            f"Sectors missing     : {run_profile.sectors_missing}",
            f"Rotation state      : {run_profile.rotation_state}",
            f"Leadership state    : {run_profile.leadership_state}",
            f"Confidence          : {run_profile.confidence:.6f}",
            f"Governance          : {run_profile.governance_status}",
            f"Output              : {run_profile.output_path}",
        ]
    )
