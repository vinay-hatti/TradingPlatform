# UI Milestone 8 Nullability Fix

Fixes TypeScript TS18047 in `MarketOverviewRefinedPage.tsx` by normalizing `risk_alerts` into a local `riskAlerts` array before rendering. This avoids dereferencing nullable `data` after an optional-chain length check.
