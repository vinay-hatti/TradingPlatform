from datetime import date

from trading_ai.scanner.sector_leadership_rotation.contracts import (
    SectorLeadershipGovernanceStatus,
)
from trading_ai.scanner.sector_leadership_rotation.engine import (
    SectorLeadershipEngine,
)


def sector(
    symbol,
    group,
    return_5d,
    return_21d,
    relative_strength,
    trend,
    strength,
):
    return {
        "symbol": symbol,
        "asset_class": "SECTOR",
        "group": group,
        "return_5d": return_5d,
        "return_21d": return_21d,
        "relative_strength_21d": relative_strength,
        "trend_direction": trend,
        "trend_strength": strength,
        "liquidity_regime": "DEEP",
        "governance_status": "READY",
    }


def main():
    records = {
        "XLK": sector("XLK", "TECHNOLOGY", .04, .12, .05, "UP", .08),
        "XLY": sector("XLY", "CONSUMER_DISCRETIONARY", .03, .10, .03, "UP", .07),
        "XLI": sector("XLI", "INDUSTRIALS", .025, .09, .02, "UP", .06),
        "XLF": sector("XLF", "FINANCIALS", .02, .08, .01, "UP", .05),
        "XLC": sector("XLC", "COMMUNICATION_SERVICES", .018, .07, .01, "UP", .05),
        "XLE": sector("XLE", "ENERGY", .01, .04, -.01, "MIXED", .02),
        "XLB": sector("XLB", "MATERIALS", .012, .05, -.005, "MIXED", .02),
        "XLV": sector("XLV", "HEALTH_CARE", -.01, -.01, -.04, "DOWN", .04),
        "XLP": sector("XLP", "CONSUMER_STAPLES", -.015, -.02, -.05, "DOWN", .05),
        "XLU": sector("XLU", "UTILITIES", -.02, -.03, -.06, "DOWN", .06),
        "XLRE": sector("XLRE", "REAL_ESTATE", -.01, -.01, -.04, "DOWN", .04),
    }

    profile = SectorLeadershipEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        features_by_symbol=records,
    )

    assert (
        profile.governance_status
        == SectorLeadershipGovernanceStatus.READY
    )
    assert profile.leadership_state == "OFFENSIVE"
    assert profile.rotation_state in {
        "BROAD_RISK_ON",
        "NARROW_RISK_ON",
    }
    assert profile.leaders[0] == "XLK"
    assert "XLU" in profile.laggards or "XLP" in profile.laggards
    assert profile.offensive_leadership_score > profile.defensive_leadership_score
    assert profile.rankings[0].rank == 1
    assert profile.confidence > 0

    print("Milestone 35 Phase 5 Step 3 engine assertions passed.")


if __name__ == "__main__":
    main()
