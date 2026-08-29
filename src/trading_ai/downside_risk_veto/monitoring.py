from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:json.dump(payload,fh,indent=2,sort_keys=True,default=str);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def update_prospective_outcomes(project_root: str | Path) -> dict[str, Any]:
    root=Path(project_root).expanduser().resolve();history=root/'data/downside_risk_veto/history';ledger=root/'data/downside_risk_veto/prospective_outcomes.json'
    prior={}
    if ledger.exists():
        raw=json.loads(ledger.read_text());prior={str(x['observation_id']):x for x in raw.get('observations') or []}
    snapshots=[]
    for p in sorted(history.glob('*.json')):
        try:snap=json.loads(p.read_text())
        except Exception:continue
        asof=str(snap.get('market_as_of_date') or '')[:10];run=str(snap.get('stock_scanner_run_id') or '')
        if not asof or not run:continue
        for symbol,rec in (snap.get('records') or {}).items():
            if not isinstance(rec,dict) or rec.get('trade_builder_ready_long') is not True:continue
            oid=f"{run}|{symbol}|20"
            if oid in prior:continue
            snapshots.append((oid,run,symbol,asof,rec,snap.get('model_fingerprint')))
    if snapshots:
        from trading_ai.database.session import SessionLocal
        symbols=sorted({x[2] for x in snapshots})
        first=min(x[3] for x in snapshots)
        with SessionLocal() as s:
            rows=[dict(x) for x in s.execute(text("""SELECT symbol,date,close FROM price_history
              WHERE UPPER(symbol)=ANY(:symbols) AND date>=:first AND close>0 ORDER BY symbol,date"""),{'symbols':symbols,'first':first}).mappings()]
        by={}
        for r in rows:by.setdefault(str(r['symbol']).upper(),[]).append((str(r['date'])[:10],float(r['close'])))
        for oid,run,sym,asof,rec,fp in snapshots:
            h=by.get(sym.upper()) or [];dates=[x[0] for x in h]
            try:i=dates.index(asof)
            except ValueError:continue
            if i+20>=len(h):continue
            entry=h[i][1];exitp=h[i+20][1]
            if not entry:continue
            ret=exitp/entry-1.0
            prior[oid]={
              'observation_id':oid,'stock_scanner_run_id':run,'symbol':sym,'as_of':asof,'horizon':20,
              'veto':bool(rec.get('veto')),'probability_up':rec.get('probability_up'),'cross_section_percentile':rec.get('cross_section_percentile'),
              'forward_return_20':ret,'loss_10':ret<=-0.10,'loss_20':ret<=-0.20,'model_fingerprint':fp,'matured_at':datetime.now(timezone.utc).isoformat(),
            }
    obs=sorted(prior.values(),key=lambda x:(x['as_of'],x['symbol']))
    veto=[x for x in obs if x.get('veto')];non=[x for x in obs if not x.get('veto')]
    def rate(rows,key):return None if not rows else sum(bool(x.get(key)) for x in rows)/len(rows)
    payload={'version':'M77.23-PROSPECTIVE-OUTCOME-LEDGER-1.0','updated_at':datetime.now(timezone.utc).isoformat(),'observations':obs,
      'summary':{'observation_count':len(obs),'veto_count':len(veto),'non_veto_count':len(non),'veto_loss_10_rate':rate(veto,'loss_10'),'non_veto_loss_10_rate':rate(non,'loss_10'),'veto_loss_20_rate':rate(veto,'loss_20'),'non_veto_loss_20_rate':rate(non,'loss_20')},
      'adaptive_learning_performed':False,'production_model_retrained':False}
    _atomic_json(ledger,payload);return payload
