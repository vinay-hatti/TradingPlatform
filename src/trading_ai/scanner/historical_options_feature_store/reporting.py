from __future__ import annotations


def render_console_report(profile) -> str:
    metadata = profile.metadata or {}
    price_source = metadata.get(
        "underlying_price_source",
        "unknown",
    )
    with_price = metadata.get(
        "records_with_underlying_price_features",
        0,
    )
    without_price = metadata.get(
        "records_without_underlying_price_features",
        0,
    )

    return "\n".join(
        [
            "=" * 72,
            (
                "Milestone 35 Phase 4 Step 1 — Historical Options "
                "Feature Store"
            ),
            "=" * 72,
            f"As-of date            : {profile.as_of_date}",
            f"Symbols considered    : {profile.symbols_considered}",
            f"Symbols included      : {profile.symbols_included}",
            f"Symbols excluded      : {profile.symbols_excluded}",
            f"Contracts read        : {profile.contracts_read}",
            f"Features generated    : {profile.features_generated}",
            f"READY records         : {profile.records_ready}",
            f"REVIEW records        : {profile.records_review}",
            f"EXCLUDED records      : {profile.records_excluded}",
            f"Underlying price src  : {price_source}",
            f"With price features   : {with_price}",
            f"Without price features: {without_price}",
            f"Feature output        : {profile.output_path}",
        ]
    )
