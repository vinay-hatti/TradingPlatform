# Milestone 53 Phase 4 — Option Scanner Strategy Engine

This cumulative UI package adds a governed strategy engine to the persisted-data-only Option Scanner while leaving Daily Scanner behavior intact.

## Strategy presets

- Balanced Opportunities
- Trend Following
- Pullback
- Breakout
- Reversal
- Momentum
- Gamma Squeeze
- Dealer Flow
- Income

Each preset applies real scanner parameters: governed universe preference, minimum score, result count, expiration mode, DTE range, expiry diversification, minimum open interest, minimum option volume, and maximum bid/ask spread.

## Risk profiles

- Conservative
- Balanced
- Aggressive
- Institutional

Risk profiles control risk per trade, maximum position percentage, take-profit percentage, and stop-loss percentage sent to the existing scanner API.

## Data policy

Option Scanner remains read-only and always sends `refresh_mode=cache_only` and `auto_refresh=false`. Daily Scanner retains its existing ingestion controls.

## Apply

```bash
./APPLY_M53_PHASE4_OPTION_SCANNER_STRATEGY_ENGINE.sh /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform
PYTHONPATH=src uv run python scripts/test_m53_phase4_option_scanner_strategy_engine.py
cd ui/workstation
npm run typecheck
npm test
npm run build
```
