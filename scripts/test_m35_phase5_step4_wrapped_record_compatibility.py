from dataclasses import dataclass

from trading_ai.scanner.dashboard.filter_contracts import ScannerFilter
from trading_ai.scanner.dashboard.filter_service import ScannerFilterService


@dataclass
class NormalizedRanking:
    rank: int
    source_record: dict


@dataclass
class Envelope:
    candidate: NormalizedRanking


def main() -> None:
    records = [
        NormalizedRanking(
            rank=1,
            source_record={
                "symbol": "AMZN",
                "institutional_score": 91,
                "probability_of_profit": 0.72,
                "direction": "CALL",
            },
        ),
        Envelope(
            candidate=NormalizedRanking(
                rank=2,
                source_record={
                    "symbol": "LLY",
                    "institutional_score": 84,
                    "probability_of_profit": 0.64,
                    "direction": "PUT",
                },
            )
        ),
    ]

    filters = ScannerFilter(
        min_institutional_score=85,
        directions=("CALL",),
    )
    filtered = ScannerFilterService().apply(records, filters)

    assert len(filtered) == 1
    assert (
        ScannerFilterService()._text(filtered[0], "symbol")
        == "AMZN"
    )

    print(
        "Milestone 35 Phase 5 Step 4 wrapped-record assertions passed."
    )


if __name__ == "__main__":
    main()
