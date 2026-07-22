import csv,json
from dataclasses import asdict,is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path
def _v(x):
    if isinstance(x,Enum):return x.value
    if isinstance(x,date):return x.isoformat()
    if is_dataclass(x):return {k:_v(v) for k,v in asdict(x).items()}
    if isinstance(x,dict):return {str(k):_v(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [_v(v) for v in x]
    return x
def write_database_validation_json(profile,path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(_v(profile),indent=2,sort_keys=True));return p
def write_database_validation_csv(profile,path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);fields=['underlying_symbol','quote_date','expiration_date','strike','option_side','valid','error_count','warning_count','issue_codes','bid','ask','last','volume','open_interest','implied_volatility','delta','gamma','theta','vega']
    with p.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
        for r in profile.validation_results:
            q=r.record;w.writerow({'underlying_symbol':q.identity.underlying_symbol,'quote_date':q.quote_date.isoformat(),'expiration_date':q.identity.expiration_date.isoformat(),'strike':q.identity.strike,'option_side':q.identity.option_side.value,'valid':r.valid,'error_count':r.error_count,'warning_count':r.warning_count,'issue_codes':';'.join(i.code for i in r.issues),'bid':q.bid,'ask':q.ask,'last':q.last,'volume':q.volume,'open_interest':q.open_interest,'implied_volatility':q.implied_volatility,'delta':q.delta,'gamma':q.gamma,'theta':q.theta,'vega':q.vega})
    return p
def write_missing_symbols_csv(profile,path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8') as h:
        w=csv.writer(h);w.writerow(['symbol']);[w.writerow([s]) for s in profile.missing_symbols]
    return p
