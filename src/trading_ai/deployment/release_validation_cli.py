from __future__ import annotations

import argparse
import json
from pathlib import Path


def _inspect(args):
    payload = json.loads(Path(args.result).read_text(encoding='utf-8'))
    print(json.dumps(payload.get('recommendation'), indent=2))
    return 0 if payload.get('ready') else 2


def register_release_validation_commands(subparsers):
    release = subparsers.add_parser(
        'release-validation', help='Release validation and readiness governance.'
    )
    commands = release.add_subparsers(dest='release_validation_command', required=True)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('--result', required=True)
    inspect.set_defaults(func=_inspect)


def main(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)
    register_release_validation_commands(subparsers)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
