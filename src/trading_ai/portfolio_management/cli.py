from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .service import PortfolioRegistryService


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Milestone 36 Phase 1 portfolio registry")
    root.add_argument("--registry-file", type=Path, default=Path("data/portfolio/m36_portfolio_registry.json"))
    sub = root.add_subparsers(dest="command", required=True)

    init = sub.add_parser("initialize")
    init.add_argument("--name", default="Primary Options Portfolio")
    init.add_argument("--portfolio-id", default="PRIMARY")
    init.add_argument("--initial-capital", type=float, required=True)

    show = sub.add_parser("show")

    add = sub.add_parser("register-position")
    add.add_argument("--symbol", required=True)
    add.add_argument("--strategy-id", required=True)
    add.add_argument("--strategy-type", required=True)
    add.add_argument("--direction", required=True)
    add.add_argument("--quantity", type=int, required=True)
    add.add_argument("--entry-price", type=float, required=True)
    add.add_argument("--capital-committed", type=float, required=True)
    add.add_argument("--maximum-loss", type=float)
    add.add_argument("--maximum-profit", type=float)
    add.add_argument("--sector", default="UNKNOWN")
    add.add_argument("--industry", default="UNKNOWN")
    add.add_argument("--correlation-group", default="")

    mark = sub.add_parser("mark-position")
    mark.add_argument("--position-id", required=True)
    mark.add_argument("--current-price", type=float, required=True)

    close = sub.add_parser("close-position")
    close.add_argument("--position-id", required=True)
    close.add_argument("--exit-price", type=float, required=True)
    return root


def run(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    service = PortfolioRegistryService(args.registry_file)
    if args.command == "initialize":
        snapshot = service.initialize(args.name, args.initial_capital, args.portfolio_id)
    elif args.command == "show":
        snapshot = service.load_snapshot()
    elif args.command == "register-position":
        snapshot = service.register_position(
            symbol=args.symbol,
            strategy_id=args.strategy_id,
            strategy_type=args.strategy_type,
            direction=args.direction,
            quantity=args.quantity,
            entry_price=args.entry_price,
            capital_committed=args.capital_committed,
            maximum_loss=args.maximum_loss,
            maximum_profit=args.maximum_profit,
            sector=args.sector,
            industry=args.industry,
            correlation_group=args.correlation_group,
        )
    elif args.command == "mark-position":
        snapshot = service.mark_position(args.position_id, args.current_price)
    else:
        snapshot = service.close_position(args.position_id, args.exit_price)
    print(json.dumps(snapshot.to_dict(), indent=2))
    return 0
