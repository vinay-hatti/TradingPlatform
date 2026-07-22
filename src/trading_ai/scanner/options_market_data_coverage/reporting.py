from __future__ import annotations

from .contracts import OptionChainCoverageRunProfile


def render_console_report(
    profile: OptionChainCoverageRunProfile,
) -> str:
    lines = [
        "=" * 72,
        "Milestone 35 Phase 3 Step 3 — Option-Chain Coverage",
        "=" * 72,
        f"As-of date            : {profile.as_of_date}",
        f"Symbols evaluated     : {profile.symbols_evaluated}",
        f"READY                 : {profile.ready_symbols}",
        f"REVIEW                : {profile.review_symbols}",
        f"FAILED                : {profile.failed_symbols}",
        f"Average coverage      : {profile.average_coverage_score:.2%}",
        f"Minimum coverage      : {profile.minimum_coverage_score:.2%}",
        f"Maximum coverage      : {profile.maximum_coverage_score:.2%}",
    ]

    weakest = sorted(
        profile.profiles,
        key=lambda item: (
            item.overall_coverage_score,
            item.symbol,
        ),
    )[:10]

    if weakest:
        lines.extend(["", "Weakest symbols:"])
        for item in weakest:
            lines.append(
                f"  {item.symbol:<8} "
                f"{item.governance_status.value:<6} "
                f"score={item.overall_coverage_score:.3f} "
                f"contracts={item.contract_count} "
                f"expirations={item.expiration_count} "
                f"strikes={item.distinct_strike_count}"
            )

    return "\n".join(lines)
