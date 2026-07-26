# Milestone 47 Phase 2 — Install and Validate

Install over Milestone 47 Phase 1.

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_Milestone47_Phase2_DailyScannerPublishedState_20260725.tar.gz --strip-components=1
```

Validate:

```bash
uv run python scripts/test_m47_phase1_published_state_resolver.py
uv run python scripts/test_m47_phase2_daily_scanner_published_state.py
```

Normal daily scan resolves and enforces `current_market_state` automatically. Your current DEGRADED publication is accepted because scanner readiness is true.

```bash
uv run python scripts/run_daily_scan.py --symbols AAPL,MSFT,AMZN --top 10
```

Strict READY-only mode:

```bash
uv run python scripts/run_daily_scan.py --symbols AAPL,MSFT,AMZN --require-ready-published-state
```

Emergency compatibility override only:

```bash
uv run python scripts/run_daily_scan.py --symbols AAPL,MSFT,AMZN --allow-unpublished-state
```
