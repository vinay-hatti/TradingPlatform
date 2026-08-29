#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from trading_ai.downside_risk_veto.monitoring import update_prospective_outcomes

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',default='/Users/vinay.hatti/TradingPlatform');a=p.parse_args();r=update_prospective_outcomes(a.project_root);print(json.dumps(r['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
