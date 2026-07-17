from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "pyproject.toml",
    "alembic.ini",
    "src/trading_ai/__main__.py",
    "scripts/run_market_ingestion.py",
    "scripts/run_indicators.py",
    "scripts/run_daily_scan.py",
    "scripts/run_paper_daily.py",
    "scripts/paper_trade_from_optimizer.py",
    "scripts/mark_paper_positions.py",
    "scripts/paper_status.py",
    "scripts/build_dashboard.py",
)

REQUIRED_MODULES = (
    "numpy",
    "pandas",
    "sqlalchemy",
    "pydantic",
    "dotenv",
)


def status(ok: bool, label: str, detail: str = "") -> None:
    marker = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{marker}] {label}{suffix}")


def check_tcp(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local TradingPlatform setup.")
    parser.add_argument("--skip-db", action="store_true")
    args = parser.parse_args()

    failures = 0

    status(sys.version_info >= (3, 13), "Python >= 3.13", sys.version.split()[0])
    failures += sys.version_info < (3, 13)

    uv = shutil.which("uv")
    status(bool(uv), "uv installed", uv or "not found")
    failures += not bool(uv)

    for rel in REQUIRED_FILES:
        exists = (ROOT / rel).is_file()
        status(exists, rel)
        failures += not exists

    env_path = ROOT / ".env"
    status(env_path.is_file(), ".env present")
    failures += not env_path.is_file()

    for module in REQUIRED_MODULES:
        found = importlib.util.find_spec(module) is not None
        status(found, f"Python module: {module}")
        failures += not found

    try:
        import trading_ai
        status(True, "trading_ai package import", str(Path(trading_ai.__file__).resolve()))
    except Exception as exc:
        status(False, "trading_ai package import", repr(exc))
        failures += 1

    if not args.skip_db:
        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "5432"))
        reachable = check_tcp(host, port)
        status(reachable, "PostgreSQL TCP connectivity", f"{host}:{port}")
        failures += not reachable

    print()
    if failures:
        print(f"Local setup check completed with {failures} failure(s).")
        return 1
    print("Local setup check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
