from __future__ import annotations


def render_console_report(profile) -> str:
    lines = [
        "=" * 72,
        "Milestone 35 Phase 3 Step 5 — Consolidated Option-Data Readiness",
        "=" * 72,
        f"As-of date            : {profile.as_of_date}",
        f"Symbols evaluated     : {profile.symbols_evaluated}",
        f"READY                 : {profile.ready_symbols}",
        f"REVIEW                : {profile.review_symbols}",
        f"FAILED                : {profile.failed_symbols}",
        f"Average readiness     : {profile.average_readiness_score:.2%}",
        f"Minimum readiness     : {profile.minimum_readiness_score:.2%}",
        f"Maximum readiness     : {profile.maximum_readiness_score:.2%}",
        f"Coverage report       : {profile.coverage_report_path}",
        f"Quality report        : {profile.quality_report_path}",
    ]

    weakest = sorted(
        profile.profiles,
        key=lambda item: (item.readiness_score, item.symbol),
    )[:10]

    if weakest:
        lines.extend(["", "Weakest symbols:"])
        for item in weakest:
            lines.append(
                f"  {item.symbol:<8} "
                f"{item.readiness_status.value:<6} "
                f"readiness={item.readiness_score:.3f} "
                f"coverage={item.coverage_score:.3f} "
                f"quality={item.quality_score:.3f}"
            )

    return "\n".join(lines)
