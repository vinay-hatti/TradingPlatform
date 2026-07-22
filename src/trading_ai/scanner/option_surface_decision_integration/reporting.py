from __future__ import annotations


def render_console_report(profile) -> str:
    return "\n".join(
        [
            "=" * 72,
            (
                "Milestone 35 Phase 4 Step 4 — Option Surface "
                "Decision Integration"
            ),
            "=" * 72,
            f"As-of date            : {profile.as_of_date}",
            f"Records read          : {profile.records_read}",
            f"Records generated     : {profile.records_generated}",
            f"ELIGIBLE               : {profile.eligible_count}",
            f"REVIEW                 : {profile.review_count}",
            f"BLOCKED                : {profile.blocked_count}",
            f"Decision feature output: {profile.output_path}",
        ]
    )
