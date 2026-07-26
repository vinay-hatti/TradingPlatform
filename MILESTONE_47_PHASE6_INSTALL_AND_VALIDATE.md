# Install and Validate Milestone 47 Phase 6

```bash
cd /Users/vinay.hatti/TradingPlatform

tar -xzf ~/Downloads/TradingPlatform_Milestone47_Phase6_ReportingIntegration_20260725.tar.gz \
  --strip-components=1
```

No database migration is required after Phase 5 migration `m47_001`.

Run validation:

```bash
uv run python scripts/test_m47_phase6_reporting_integration.py
```

Run the normal scanner and inspect the printed manifest paths:

```bash
uv run python scripts/run_daily_scan.py --symbols AAPL,MSFT,AMZN --top 10
```

Confirm the HTML files contain `Published Market State` and `Governance Summary`, and confirm both manifest files contain non-empty SHA-256 values.
