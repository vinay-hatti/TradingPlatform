from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'src/trading_ai/institutional_market_structure/engine.py').read_text()
block=source[source.index('def _gamma_flip_grid'):source.index('@staticmethod\n    def _slope')]
checks={
    'gamma-only shock calculation':'_greeks(' not in block and 'gamma=_pdf(d1)/(s*iv*rt)' in block,
    'grid resolution preserved':'self.policy.gamma_grid_steps' in block,
    'grid range preserved':'self.policy.gamma_grid_min_factor' in block and 'self.policy.gamma_grid_max_factor' in block,
    'exposure formula preserved':'total+=sign*gamma*oi*multiplier*s*s*.01' in block,
    'estimator version unchanged':"ESTIMATOR_VERSION='44.2.1'" in source,
}
failed=[k for k,v in checks.items() if not v]
if failed:
    raise SystemExit('M68.2.1.15.8.6 verification FAILED: '+', '.join(failed))
print('M68.2.1.15.8.6 source verification PASSED')
for k in checks: print(' - '+k)
