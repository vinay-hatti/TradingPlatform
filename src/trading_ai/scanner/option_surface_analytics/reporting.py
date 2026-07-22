from __future__ import annotations


def render_console_report(profile) -> str:
    return "\n".join(
        [
            "=" * 72,
            (
                "Milestone 35 Phase 4 Step 2 — Option Surface "
                "and Volatility Analytics"
            ),
            "=" * 72,
            f"As-of date            : {profile.as_of_date}",
            f"Contracts read        : {profile.contracts_read}",
            f"Contracts eligible    : {profile.contracts_eligible}",
            f"Contracts excluded    : {profile.contracts_excluded}",
            f"Symbols evaluated     : {profile.symbols_evaluated}",
            f"Expirations evaluated : {profile.expirations_evaluated}",
            f"Expiration READY      : {profile.expiration_ready}",
            f"Expiration REVIEW     : {profile.expiration_review}",
            f"Expiration EXCLUDED   : {profile.expiration_excluded}",
            f"Symbol READY          : {profile.symbol_ready}",
            f"Symbol REVIEW         : {profile.symbol_review}",
            f"Symbol EXCLUDED       : {profile.symbol_excluded}",
            f"Expiration output     : {profile.expiration_output_path}",
            f"Symbol output         : {profile.symbol_output_path}",
        ]
    )
