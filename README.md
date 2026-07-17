# Trading AI Platform

Institutional options research, backtesting, paper-trading, risk, and portfolio platform.

## Local Mac bootstrap

```bash
cd /Users/vinay.hatti/TradingPlatform
brew services start postgresql@17
uv sync
uv run alembic upgrade head
uv run python -m trading_ai local-doctor
```

After `uv sync`, either command form works:

```bash
uv run python -m trading_ai --help
uv run trading-ai --help
```

## Local workflows

Run a one-time paper workflow:

```bash
uv run python -m trading_ai start --mode paper
```

Research workflow:

```bash
uv run python -m trading_ai start --mode research
```

Daily workflow already provided by the repository:

```bash
uv run python -m trading_ai daily
```

Run each stage independently:

```bash
uv run python -m trading_ai ingest-market
uv run python -m trading_ai build-features
uv run python -m trading_ai generate-signals
uv run python -m trading_ai full-system
uv run python -m trading_ai paper run
uv run python -m trading_ai paper mark
uv run python -m trading_ai paper status
uv run python -m trading_ai dashboard
```

Start the Streamlit dashboard runner:

```bash
uv run python -m trading_ai dashboard-server
```

## Important behavior

`start` runs existing repository scripts in sequence. It is a one-time local
workflow, not a permanently running server. External market-data calls still
require the provider credentials and configuration expected by the existing
scripts.
