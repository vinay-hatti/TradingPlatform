from __future__ import annotations

from .contracts import OptionChainQualityRunProfile


def render_console_report(profile: OptionChainQualityRunProfile) -> str:
    lines = [
        "=" * 72,
        "Milestone 35 Phase 3 Step 4 — Option-Chain Quality",
        "=" * 72,
        f"As-of date            : {profile.as_of_date}",
        f"Symbols evaluated     : {profile.symbols_evaluated}",
        f"READY                 : {profile.ready_symbols}",
        f"REVIEW                : {profile.review_symbols}",
        f"FAILED                : {profile.failed_symbols}",
        f"Average quality       : {profile.average_quality_score:.2%}",
        f"Minimum quality       : {profile.minimum_quality_score:.2%}",
        f"Maximum quality       : {profile.maximum_quality_score:.2%}",
        f"Total contracts       : {profile.total_contracts}",
        f"Quoted contracts      : {profile.quoted_contracts}",
        f"NBBO observed         : {'YES' if profile.quote_data_observed else 'NO'}",
    ]
    if not profile.quote_data_observed:
        lines.extend([
            "",
            "Provider capability note:",
            "  NBBO bid/ask data was not observed. Quote and spread dimensions",
            "  were excluded from scoring and governance rather than scored as zero.",
        ])

    weakest = sorted(
        profile.profiles,
        key=lambda item: (item.overall_quality_score, item.symbol),
    )[:10]
    if weakest:
        lines.extend(["", "Weakest symbols:"])
        for item in weakest:
            lines.append(
                f"  {item.symbol:<8} {item.governance_status.value:<6} "
                f"score={item.overall_quality_score:.3f} "
                f"contracts={item.contract_count} "
                f"liquidity={item.liquidity_score:.3f} "
                f"greeks={item.greeks_completeness_score:.3f}"
            )
    return "\n".join(lines)
