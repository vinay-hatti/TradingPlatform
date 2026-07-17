Given the state of your project and everything we've built together, I would **not** recommend trying to run the entire platform in one shot immediately. The platform now spans:

* Research Engine
* Institutional Decision Engine
* Market Data Layer
* Portfolio Management
* Risk Engine
* Broker Integration
* Order Management
* Paper Trading
* Monitoring
* Observability
* Deployment Governance
* Operational Governance
* Production Readiness

A much better approach is to bring it up in **layers**, validating each subsystem before enabling the next. This mirrors how institutional trading systems are deployed.

---

# Phase 1 — Prepare the Mac

## 1. Install Xcode Command Line Tools

```bash
xcode-select --install
```

---

## 2. Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Verify:

```bash
brew doctor
```

---

## 3. Install Python

You are already using Python 3.13.

Verify:

```bash
python3 --version
```

---

## 4. Install uv

```bash
brew install uv
```

Verify

```bash
uv --version
```

---

## 5. Install PostgreSQL

```bash
brew install postgresql@17
```

Start

```bash
brew services start postgresql@17
```

Verify

```bash
psql --version
```

---

## 6. Install Git

```bash
brew install git
```

---

## 7. Optional Tools

Useful during development

```bash
brew install jq
brew install tree
brew install htop
brew install watch
```

---

# Phase 2 — Clone Project

```bash
git clone https://github.com/vinay-hatti/TradingPlatform.git
```

```bash
cd TradingPlatform
```

---

# Phase 3 — Create Virtual Environment

```bash
uv venv
```

Activate

```bash
source .venv/bin/activate
```

Verify

```bash
python --version
```

---

# Phase 4 — Install Dependencies

If your project already contains

```
pyproject.toml
```

run

```bash
uv sync
```

Otherwise

```bash
uv pip install -e .
```

---

Verify

```bash
python -m trading_ai --help
```

---

# Phase 5 — Configure PostgreSQL

Create database

```bash
createdb trading_ai
```

Connect

```bash
psql trading_ai
```

---

Create user if needed

```sql
CREATE USER trading_user WITH PASSWORD 'password';
```

Grant permissions

```sql
GRANT ALL PRIVILEGES ON DATABASE trading_ai TO trading_user;
```

Exit

```
\q
```

---

# Phase 6 — Configure Environment

Create

```
.env
```

Example

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_ai
DB_USER=trading_user
DB_PASSWORD=password

ENVIRONMENT=development

LOG_LEVEL=INFO

SECRET_KEY=replace_me

MARKET_DATA_PROVIDER=PAPER

BROKER=PAPER
```

---

# Phase 7 — Alembic

Initialize database

```bash
uv run alembic upgrade head
```

Expected

```
Running upgrade ...
```

---

Verify

```bash
psql trading_ai
```

```
\dt
```

You should see all project tables.

---

# Phase 8 — Install Python Packages

Verify

```bash
uv pip list
```

Should include packages such as:

```
numpy
pandas
SQLAlchemy
Alembic
yfinance
pydantic
scipy
matplotlib
```

---

# Phase 9 — Verify Core Services

Run

```bash
uv run python scripts/test_repository.py
```

Expected

```
Repository tests passed
```

---

Then

```bash
uv run python scripts/test_features.py
```

Expected

```
Feature pipeline passed
```

---

# Phase 10 — Verify Milestone 29

Run

```bash
uv run python scripts/test_walk_forward_governance_reporting.py
```

Then

```bash
uv run python scripts/test_execution_analytics.py
```

Then

```bash
uv run python scripts/test_market_regime_detection.py
```

All should pass.

---

# Phase 11 — Verify Milestone 30

Run sequentially:

```bash
uv run python scripts/test_deployment_governance.py
```

```bash
uv run python scripts/test_release_validation_readiness.py
```

```bash
uv run python scripts/test_deployment_automation.py
```

```bash
uv run python scripts/test_operational_governance.py
```

```bash
uv run python scripts/test_final_project_closure.py
```

Finally

```bash
uv run python scripts/test_milestone30_phase10_step5_regression.py
```

---

# Phase 12 — Generate Reports

Run:

```bash
uv run python scripts/run_final_performance_benchmarks.py
```

Expected output:

```
reports/
```

containing:

```
final_performance_benchmarks.json
```

---

# Phase 13 — Start the Platform

## Import Historical Data

```bash
uv run python -m trading_ai import-price-history
```

---

## Import Option Chains

```bash
uv run python -m trading_ai import-option-chain
```

---

## Generate Features

```bash
uv run python -m trading_ai build-features
```

---

## Generate Signals

```bash
uv run python -m trading_ai generate-signals
```

---

## Run Decision Engine

```bash
uv run python -m trading_ai institutional-decision
```

---

## Run Paper Trading

```bash
uv run python -m trading_ai paper-trading
```

---

## Run Monitoring

```bash
uv run python -m trading_ai monitoring
```

---

# Daily Workflow

Once everything is configured, a typical daily development workflow looks like this:

```bash
git pull

source .venv/bin/activate

uv sync

brew services start postgresql@17

uv run alembic upgrade head

uv run python scripts/test_milestone30_phase10_step5_regression.py

uv run python -m trading_ai paper-trading
```

---

# Recommended Future Enhancements

Before moving from paper trading to live trading, I recommend adding these production-grade components:

1. **FastAPI REST API** for controlling and monitoring the platform remotely.
2. **Web Dashboard** (e.g., React or Streamlit) for live positions, P&L, Greeks, and risk visualization.
3. **Docker Compose** to package PostgreSQL, Redis, Prometheus, Grafana, and the application for reproducible deployments.
4. **Real broker adapters** (Interactive Brokers, Tastytrade, Tradier, etc.) with sandbox validation before live execution.
5. **Redis and Celery (or another task queue)** to support asynchronous market data ingestion and order processing.
6. **Automated CI/CD** with GitHub Actions to run the regression suite on every commit.

These additions are not strictly required to run the platform locally, but they will significantly improve maintainability and prepare the project for a robust production deployment.

