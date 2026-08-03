# Milestone 59 — Institutional Execution Workspace

## Workflow

Option Scanner → Opportunity → Institutional Intelligence → Trade Builder → Execution Workspace → IBKR Paper → Portfolio Intelligence.

Trade Builder creates a versioned execution intent after a plan becomes `PAPER_READY`. The OMS validates paper routing, risk, buying power, and leg structure. Submission requires the exact operator phrase `SUBMIT PAPER INTENT <intent-id>`.

## Safety boundary

- PAPER environment only.
- IBKR paper account must begin with `DU`.
- Existing paper-routing activation must be enabled.
- Live trading remains disabled.
- Direct submission currently supports one option leg. Multi-leg plans remain in the queue with a warning until atomic IBKR BAG/combo support is enabled; the system will not leg into a spread silently.

## Lifecycle

`PAPER_READY → VALIDATED → APPROVED → SUBMITTED → ACKNOWLEDGED/PARTIALLY_FILLED → FILLED`

Terminal states: `FILLED`, `CANCELLED`, `REJECTED`, `EXPIRED`.

## Position creation

When broker synchronization observes a full fill, the execution intent is marked `FILLED` and Portfolio Intelligence creates an idempotent managed position using the trade-plan lineage and broker fill details.
