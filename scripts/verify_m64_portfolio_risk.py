from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.service import PortfolioRiskAllocationService

svc = PortfolioRiskAllocationService(SessionLocal)
r = svc.build("PAPER-PRIMARY")
p = r["payload_json"]
position_count = int(p.get("position_count") or 0)
greeks = p.get("greeks") or {}
quality = p.get("data_quality") or {}
nonzero_greeks = any(abs(float(greeks.get(k) or 0)) > 1e-9 for k in ("delta", "gamma", "theta", "vega", "rho"))
positions = p.get("positions") or []
structures = p.get("structures") or []
industries = p.get("exposures", {}).get("industry", {}) or {}
market_metrics_available = any(
    float(row.get("realized_volatility_20d") or 0) > 0
    or abs(float(row.get("beta") or 0) - 1.0) > 1e-6
    for row in positions
)
repeated_symbols = len({row.get("symbol") for row in positions}) < len(positions)
checks = {
    "snapshot": bool(r.get("snapshot_id")),
    "positions": position_count > 0,
    "option_quote_enrichment": float(quality.get("exact_option_quote_coverage_pct") or 0) > 0,
    "economic_greeks": nonzero_greeks,
    "sector_enrichment": "UNKNOWN" not in (p.get("exposures", {}).get("sector", {}) or {}) or len((p.get("exposures", {}).get("sector", {}) or {})) > 1,
    "industry_enrichment": bool(industries) and not (len(industries) == 1 and "UNKNOWN" in industries),
    "market_metrics": market_metrics_available,
    "structure_reconstruction": (not repeated_symbols) or bool(structures),
    "delta_gamma_vega_var": p.get("risk", {}).get("methodology") == "DELTA_GAMMA_VEGA_1D_PROXY" and r["var_95"] >= 0,
    "stress": bool(svc.stress("PAPER-PRIMARY")["scenarios"]),
}
print("\n".join(f'{k}: {"PASS" if v else "FAIL"}' for k, v in checks.items()))
print(f'Exact option quote coverage: {float(quality.get("exact_option_quote_coverage_pct") or 0):.1f}%')
print(f'Governed/reconstructed classification coverage: {float(quality.get("governed_classification_coverage_pct") or 0):.1f}%')
print(f'Reconstructed multi-leg structures: {len(structures)}')
if quality.get("warnings"):
    print("Data-quality warnings:")
    for warning in quality["warnings"][:20]:
        print(f"  - {warning}")
assert all(checks.values()), "Milestone 64 institutional risk acceptance FAILED"
print("Milestone 64 institutional risk acceptance PASSED")
