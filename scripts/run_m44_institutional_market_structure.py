from __future__ import annotations
import argparse,json
from datetime import date
from pathlib import Path
from trading_ai.institutional_market_structure import DealerPositioningPolicy

def main()->None:
    p=argparse.ArgumentParser(description='Milestone 44 persisted-snapshot institutional market structure and dealer positioning analytics')
    p.add_argument('--symbol',required=True)
    p.add_argument('--as-of',default=date.today().isoformat())
    p.add_argument('--output-dir',default='reports/m44')
    p.add_argument('--minimum-dte',type=int,default=1)
    p.add_argument('--maximum-dte',type=int,default=365)
    p.add_argument('--maximum-snapshot-age-days',type=int,default=3)
    p.add_argument('--dealer-sign-convention',choices=['street_proxy','customer_long_proxy','unsigned_market_exposure'],default='street_proxy')
    p.add_argument('--no-persist',action='store_true')
    a=p.parse_args()
    from trading_ai.institutional_market_structure import InstitutionalMarketStructureService
    policy=DealerPositioningPolicy(minimum_dte=a.minimum_dte,maximum_dte=a.maximum_dte,maximum_snapshot_age_days=a.maximum_snapshot_age_days,dealer_sign_convention=a.dealer_sign_convention)
    s=InstitutionalMarketStructureService(policy).run(a.symbol,date.fromisoformat(a.as_of),Path(a.output_dir),persist=not a.no_persist)
    keys=('symbol','as_of_date','option_snapshot_date','source_contract_count','executable_contract_count','quote_coverage_pct','positioning_label','gamma_regime','gamma_flip','primary_call_wall','primary_put_wall','institutional_positioning_score','bull_probability','bear_probability','range_probability','breakout_probability','confidence')
    print(json.dumps({k:s.to_dict()[k] for k in keys},indent=2))
if __name__=='__main__':main()
