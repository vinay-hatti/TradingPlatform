## Trading AI Commands

### Scanner

```bash
uv run python -m trading_ai scan --only-affordable --min-confidence A --min-days-to-expiry 45


### Optimizer
uv run python -m trading_ai optimize

### Option Details
uv run python -m trading_ai option-details

### Paper Trading
uv run python -m trading_ai paper run
uv run python -m trading_ai paper mark
uv run python -m trading_ai paper status
uv run python -m trading_ai paper reset

### Daily Workflow
uv run python -m trading_ai daily
open reports/dashboard.html
--OR--
./run_paper_daily.sh
