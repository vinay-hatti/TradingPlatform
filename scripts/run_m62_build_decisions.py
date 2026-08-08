from __future__ import annotations

import argparse

from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.decision import InstitutionalDecisionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Build immutable Milestone 62 institutional decision snapshots")
    parser.add_argument("--opportunity-ids", default="", help="Comma-separated opportunity IDs; default processes all eligible rows")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    ids = [item.strip() for item in args.opportunity_ids.split(",") if item.strip()] or None
    with SessionLocal() as session:
        result = InstitutionalDecisionService(session).build(opportunity_ids=ids, limit=args.limit)
        session.commit()
        print(result)


if __name__ == "__main__":
    main()
