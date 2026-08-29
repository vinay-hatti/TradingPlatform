#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from trading_ai.downside_risk_veto.live_authority import refresh_live_authority

def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',default='/Users/vinay.hatti/TradingPlatform');a=p.parse_args()
    print(json.dumps(refresh_live_authority(a.project_root),indent=2,sort_keys=True,default=str));return 0
if __name__=='__main__':raise SystemExit(main())
