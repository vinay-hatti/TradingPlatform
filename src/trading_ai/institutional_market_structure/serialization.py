from __future__ import annotations
import csv,json
from pathlib import Path
from .contracts import ExpirationExposure,HistoricalComparison,InstitutionalMarketStructureSnapshot,IVSurfacePoint,MetricProvenance,StrikeExposure

def write_snapshot(snapshot,output_dir:Path):
    output_dir.mkdir(parents=True,exist_ok=True); base=f'{snapshot.symbol.lower()}_{snapshot.as_of_date}'
    jp=output_dir/f'{base}.json'; jp.write_text(json.dumps(snapshot.to_dict(),indent=2,allow_nan=False),encoding='utf-8')
    paths={'json':jp}
    for name,rows in [('strikes',snapshot.strike_exposures),('expirations',snapshot.expiration_exposures),('iv_surface',snapshot.iv_surface)]:
        p=output_dir/f'{base}_{name}.csv'; data=[x.__dict__ for x in rows]
        with p.open('w',newline='',encoding='utf-8') as h:
            w=csv.DictWriter(h,fieldnames=list(data[0]) if data else ['symbol']); w.writeheader(); w.writerows(data)
        paths[f'{name}_csv']=p
    return paths

def snapshot_from_dict(d):
    d=dict(d)
    d['strike_exposures']=tuple(StrikeExposure(**x) for x in d.get('strike_exposures',()))
    d['expiration_exposures']=tuple(ExpirationExposure(**x) for x in d.get('expiration_exposures',()))
    d['iv_surface']=tuple(IVSurfacePoint(**x) for x in d.get('iv_surface',()))
    d['provenance']=tuple(MetricProvenance(**x) for x in d.get('provenance',()))
    d['historical_comparison']=HistoricalComparison(**d.get('historical_comparison',{}))
    d['assumptions']=tuple(d.get('assumptions',())); d['warnings']=tuple(d.get('warnings',()))
    return InstitutionalMarketStructureSnapshot(**d)
