#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from trading_ai.database.session import SessionLocal
from trading_ai.outcome_probability.operator import result_exit_code
from trading_ai.outcome_probability.service import OutcomeProbabilityService


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Operate governed M77 outcome-probability shadow intelligence"
    )
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("audit", help="Report point-in-time label and training readiness")
    materialize = commands.add_parser("materialize", help="Materialize eligible barrier outcomes")
    materialize.add_argument("--max-candidates", type=int)
    train = commands.add_parser("train", help="Train a chronological challenger without activating it")
    train.add_argument("--model-version")
    approve = commands.add_parser("approve-shadow", help="Approve an evaluated challenger for shadow use")
    approve.add_argument("--model-id", required=True)
    approve.add_argument("--actor", required=True)
    approve.add_argument("--reason", required=True)
    activate = commands.add_parser("activate-shadow", help="Activate an approved model in no-authority shadow mode")
    activate.add_argument("--model-id", required=True)
    activate.add_argument("--actor", required=True)
    activate.add_argument("--reason", required=True)
    commands.add_parser("status", help="Show models, active shadow model, and evidence readiness")
    return value


def main() -> int:
    args = parser().parse_args()
    with SessionLocal() as session:
        service = OutcomeProbabilityService(session)
        if args.command == "audit":
            result = service.data_readiness()
        elif args.command == "materialize":
            result = service.materialize_outcomes(max_candidates=args.max_candidates)
        elif args.command == "train":
            result = service.train_challenger(model_version=args.model_version)
        elif args.command == "approve-shadow":
            result = service.approve_shadow_model(
                args.model_id,
                actor=args.actor,
                reason=args.reason,
            )
        elif args.command == "activate-shadow":
            result = service.activate_shadow_model(
                args.model_id,
                actor=args.actor,
                reason=args.reason,
            )
        else:
            result = service.status()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return result_exit_code(args.command, result)


if __name__ == "__main__":
    raise SystemExit(main())
