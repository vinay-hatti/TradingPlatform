# Milestone 62 Phase 10 — Dynamic Position Management & Automated Exit Engine

Phase 10 closes the fill-to-exit lifecycle for Institutional Options trades.

## Safety model

Every managed position has one of three modes:

- `ADVISORY` — evaluate and persist exit recommendations; no broker order is sent.
- `SEMI_AUTOMATIC` — triggered exits wait for explicit approval; approval may submit the paper closing order.
- `FULLY_AUTOMATIC` — triggered exits are submitted automatically, but only for paper-managed positions with verified IBKR binding and exact option identities.

The default is `ADVISORY`.

## Control loop

1. Broker synchronization confirms an entry fill.
2. The execution intent activates or reuses a `managed_positions` row.
3. Structural stop, targets, theta, volatility and emergency-loss instructions are armed in `position_exit_instructions`.
4. `run_m62_dynamic_position_management.py` reads current underlying bars and current Polygon option marks.
5. It advances a higher-low/lower-high trailing stop when structure permits.
6. It evaluates every armed rule and records an explainable management event.
7. Depending on mode, it recommends, awaits approval, or submits the paper closing order.
8. Broker synchronization and Milestone 63 reconciliation later confirm closing fills and authoritative account state.

## Run once

```bash
uv run python scripts/run_m62_dynamic_position_management.py
```

## Continuous daemon

```bash
uv run python scripts/run_m62_dynamic_position_management.py --daemon --interval-seconds 60
```

## Verify

```bash
uv run python scripts/verify_m62_phase10_dynamic_management.py
```
