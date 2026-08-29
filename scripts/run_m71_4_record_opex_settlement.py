from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from trading_ai.database.session import SessionLocal
from trading_ai.opex_intelligence.governance import settlement_convention
from trading_ai.opex_intelligence.models import OpexSettlementValueModel


VERSION = "M71.4-OFFICIAL-OPEX-SETTLEMENT-1.0"
ALLOWED_SOURCES = {
    "CBOE_OFFICIAL",
    "NASDAQ_OFFICIAL",
    "POLYGON_SPECIAL_INDEX",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record a governed official special-opening OPEX settlement value."
    )
    parser.add_argument("--symbol", choices=("SPX", "NDX", "RUT"), required=True)
    parser.add_argument("--expiration", type=date.fromisoformat, required=True)
    parser.add_argument("--value", type=float, required=True)
    parser.add_argument("--source", choices=sorted(ALLOWED_SOURCES), required=True)
    parser.add_argument("--source-reference", required=True)
    parser.add_argument("--observed-at", default=None)
    args = parser.parse_args()

    convention = settlement_convention(args.symbol, args.expiration)
    if not convention["eligible"]:
        raise SystemExit(
            f"{args.expiration} is not the governed monthly OPEX date"
        )
    if args.value <= 0:
        raise SystemExit("Settlement value must be positive")
    required_official = convention["official_source"]
    if args.source.endswith("_OFFICIAL") and not args.source.startswith(required_official):
        raise SystemExit(
            f"{args.symbol} requires {required_official} official settlement lineage"
        )

    observed_at = args.observed_at or datetime.now(timezone.utc).isoformat()
    lineage = {
        "version": VERSION,
        "source_reference": args.source_reference,
        "official_source": required_official,
        "settlement_convention": convention,
    }
    with SessionLocal() as session:
        row = session.scalar(
            select(OpexSettlementValueModel).where(
                OpexSettlementValueModel.underlying_symbol == args.symbol,
                OpexSettlementValueModel.expiration == str(args.expiration),
            )
        )
        if row and float(row.settlement_value) == float(args.value) and row.settlement_source == args.source:
            outcome = "NOOP_UNCHANGED_SETTLEMENT"
            session.rollback()
        else:
            values = {
                "settlement_symbol": convention["settlement_symbol"],
                "settlement_style": convention["settlement_style"],
                "settlement_value": args.value,
                "settlement_source": args.source,
                "observed_at": observed_at,
                "lineage_json": lineage,
            }
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
                outcome = "SETTLEMENT_UPDATED"
            else:
                row = OpexSettlementValueModel(
                    settlement_id=f"M714-SETTLE-{uuid4().hex.upper()}",
                    underlying_symbol=args.symbol,
                    expiration=str(args.expiration),
                    **values,
                )
                session.add(row)
                outcome = "SETTLEMENT_RECORDED"
            session.commit()
    print(
        json.dumps(
            {
                "status": "READY",
                "outcome": outcome,
                "symbol": args.symbol,
                "expiration": str(args.expiration),
                "settlement_symbol": convention["settlement_symbol"],
                "settlement_style": convention["settlement_style"],
                "value": args.value,
                "source": args.source,
                "version": VERSION,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
