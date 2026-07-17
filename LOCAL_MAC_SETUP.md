# Local Mac Setup and Run Guide

## 1. Install prerequisites

```bash
xcode-select --install
brew install uv postgresql@17 redis
brew services start postgresql@17
brew services start redis
```

## 2. Enter the project and install dependencies

```bash
cd /Users/vinay.hatti/TradingPlatform
uv sync
```

## 3. Configure `.env`

Keep the repository's current `.env.example` as the source of truth. At minimum,
confirm the database variables used by the project are populated:

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_ai
DB_USER=<your mac/postgres user>
DB_PASSWORD=<your password>
```

Also configure the market-data provider keys required by your current scripts.

## 4. Create and migrate PostgreSQL

```bash
createdb trading_ai 2>/dev/null || true
uv run alembic upgrade head
```

## 5. Validate the installation

```bash
uv run python -m trading_ai local-doctor
uv run python scripts/test_local_runtime_cli.py
uv run python -m trading_ai --help
```

## 6. Run locally

Recommended first pass:

```bash
uv run python -m trading_ai start --mode paper --dry-run
uv run python -m trading_ai start --mode paper
```

Available modes:

- `paper`: ingest, scan, mark existing paper positions, create paper trades, build dashboard.
- `research`: ingest, indicators/features, daily scan, build dashboard.
- `daily`: existing `run_paper_daily.py` workflow.
- `full`: ingest, indicators, full scanner/options/portfolio runner, build dashboard.

## 7. Individual commands

```bash
uv run python -m trading_ai ingest-market
uv run python -m trading_ai build-features
uv run python -m trading_ai generate-signals
uv run python -m trading_ai full-system
uv run python -m trading_ai paper status
uv run python -m trading_ai dashboard
uv run python -m trading_ai dashboard-server
```

## 8. Reports

```bash
open reports/dashboard.html
```

For the Streamlit runner, use:

```bash
uv run python -m trading_ai dashboard-server
```

## 9. Troubleshooting

Show the exact child-script arguments:

```bash
uv run python -m trading_ai backtest --help
uv run python -m trading_ai scan --help
```

Check PostgreSQL:

```bash
pg_isready -h localhost -p 5432
uv run alembic current
```

Check package resolution:

```bash
uv run python -c "import trading_ai; print(trading_ai.__file__)"
```
