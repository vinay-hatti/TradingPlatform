# Install Milestone 44

From `/Users/vinay.hatti/TradingPlatform`:

```bash
cp -R src/trading_ai/institutional_market_structure src/trading_ai/institutional_market_structure.before_m44 2>/dev/null || true
cp src/trading_ai/__main__.py src/trading_ai/__main__.py.before_m44
cp src/trading_ai/database/models.py src/trading_ai/database/models.py.before_m44
cp src/trading_ai/ui/app.py src/trading_ai/ui/app.py.before_m44

tar -xzf ~/Downloads/milestone_44_institutional_market_structure_dropin.tar.gz --strip-components=1
uv run alembic upgrade head
uv run python scripts/test_m44_institutional_market_structure.py
uv run python -m trading_ai institutional-market-structure --symbol SPY --as-of 2026-07-24
```

API:

```text
GET /api/v1/institutional-market-structure/SPY?as_of=2026-07-24
```

Reports:

```text
reports/m44/2026-07-24/
```
