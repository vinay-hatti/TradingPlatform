from __future__ import annotations


def render_console_report(profile) -> str:
    return "\n".join(
        [
            "=" * 72,
            (
                "Milestone 35 Phase 4 Step 3 — Surface Persistence "
                "and Reporting"
            ),
            "=" * 72,
            f"As-of date                 : {profile.as_of_date}",
            f"Expiration records read    : {profile.expiration_records_read}",
            f"Expiration persisted       : {profile.expiration_records_persisted}",
            f"Expiration filtered        : {profile.expiration_records_filtered}",
            f"Expiration duplicates      : {profile.duplicate_expiration_keys}",
            f"Expiration READY           : {profile.expiration_ready}",
            f"Expiration REVIEW          : {profile.expiration_review}",
            f"Expiration EXCLUDED        : {profile.expiration_excluded}",
            f"Symbol records read        : {profile.symbol_records_read}",
            f"Symbol persisted           : {profile.symbol_records_persisted}",
            f"Symbol filtered            : {profile.symbol_records_filtered}",
            f"Symbol duplicates          : {profile.duplicate_symbol_keys}",
            f"Symbol READY               : {profile.symbol_ready}",
            f"Symbol REVIEW              : {profile.symbol_review}",
            f"Symbol EXCLUDED            : {profile.symbol_excluded}",
            f"Expiration CSV             : {profile.expiration_csv_path}",
            f"Symbol CSV                 : {profile.symbol_csv_path}",
            f"Governance summary         : {profile.governance_summary_path}",
        ]
    )
