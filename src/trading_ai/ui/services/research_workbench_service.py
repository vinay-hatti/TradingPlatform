from __future__ import annotations
import csv, json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from trading_ai.ui.models.research_workbench import (
    ScannerQuery, ScannerResult, FeatureImportanceRow,
    WalkForwardRun, ReplayRequest, ReplayFrame,
)

class ResearchWorkbenchService:
    def __init__(self, reports_root: str|Path="reports", data_root: str|Path="data"):
        self.reports_root=Path(reports_root)
        self.data_root=Path(data_root)

    @staticmethod
    def _num(v: Any, default=0.0):
        try: return float(v)
        except (TypeError,ValueError): return default

    @staticmethod
    def _date(v: Any):
        try: return date.fromisoformat(str(v)[:10]) if v else None
        except Exception: return None

    def _json_files(self):
        return list(self.reports_root.rglob("*.json")) if self.reports_root.exists() else []

    def scanner(self, query: ScannerQuery):
        output=[]
        wanted={s.upper() for s in query.symbols}
        for path in self._json_files():
            if not any(x in path.name.lower() for x in ("scanner","signal","opportun","feature")): continue
            try: payload=json.loads(path.read_text())
            except Exception: continue
            items=payload if isinstance(payload,list) else payload.get("results") or payload.get("signals") or payload.get("opportunities") or []
            if not isinstance(items,list): continue
            for item in items:
                if not isinstance(item,dict): continue
                symbol=str(item.get("symbol","")).upper()
                if not symbol or (wanted and symbol not in wanted): continue
                call=self._num(item.get("call_score",item.get("score_call",0)))
                put=self._num(item.get("put_score",item.get("score_put",0)))
                signal=str(item.get("signal") or ("CALL" if call>=put else "PUT")).upper()
                confidence=max(call,put)
                if query.signal!="ALL" and signal!=query.signal: continue
                if confidence<query.min_score: continue
                output.append(ScannerResult(
                    symbol=symbol, as_of=self._date(item.get("date",item.get("as_of"))),
                    signal=signal, call_score=call, put_score=put, confidence=confidence,
                    market_regime=str(item.get("market_regime","UNKNOWN")),
                    expected_move_1d=self._num(item.get("expected_move_1d")),
                    atr14=self._num(item.get("atr14")), rsi14=self._num(item.get("rsi14")),
                    source=str(path)))
        dedup={}
        for row in output:
            key=(row.symbol,row.as_of,row.signal)
            if key not in dedup or row.confidence>dedup[key].confidence: dedup[key]=row
        return sorted(dedup.values(),key=lambda x:x.confidence,reverse=True)[:query.max_results]

    def feature_importance(self):
        values={}; directions={}
        for path in self._json_files():
            if "importance" not in path.name.lower() and "calibration" not in path.name.lower(): continue
            try: payload=json.loads(path.read_text())
            except Exception: continue
            raw=payload.get("feature_importance",payload.get("importances",payload)) if isinstance(payload,dict) else payload
            if isinstance(raw,dict):
                for name,value in raw.items():
                    if isinstance(value,dict):
                        score=self._num(value.get("importance",value.get("score")))
                        direction=str(value.get("direction","UNKNOWN")).upper()
                    else:
                        score=self._num(value); direction="UNKNOWN"
                    values[str(name)]=max(values.get(str(name),0),abs(score))
                    directions[str(name)]=direction if direction in {"POSITIVE","NEGATIVE","MIXED"} else "UNKNOWN"
        ordered=sorted(values.items(),key=lambda x:x[1],reverse=True)
        return [FeatureImportanceRow(feature=n,importance=v,rank=i+1,direction=directions.get(n,"UNKNOWN")) for i,(n,v) in enumerate(ordered)]

    def walk_forward_runs(self):
        rows=[]
        for path in self._json_files():
            if "walk" not in path.name.lower() and "metrics" not in path.name.lower(): continue
            try: payload=json.loads(path.read_text())
            except Exception: continue
            items=payload if isinstance(payload,list) else payload.get("runs",[payload])
            if not isinstance(items,list): continue
            for i,item in enumerate(items):
                if not isinstance(item,dict) or not any(k in item for k in ("net_pnl","win_rate","sharpe_ratio","max_drawdown")): continue
                rows.append(WalkForwardRun(
                    run_id=str(item.get("run_id",f"{path.stem}-{i}")), symbol=item.get("symbol"),
                    train_start=self._date(item.get("train_start")), train_end=self._date(item.get("train_end")),
                    test_start=self._date(item.get("test_start")), test_end=self._date(item.get("test_end")),
                    net_pnl=self._num(item.get("net_pnl")), win_rate=self._num(item.get("win_rate")),
                    sharpe_ratio=self._num(item.get("sharpe_ratio")), max_drawdown=self._num(item.get("max_drawdown")),
                    trades=int(self._num(item.get("trades",item.get("total_trades",0)))), source_file=str(path)))
        return rows

    def replay(self, request: ReplayRequest):
        candidates=[self.data_root/f"{request.symbol.upper()}_features.csv",self.data_root/f"{request.symbol.upper()}.csv"]
        candidates += list(self.reports_root.rglob(f"*{request.symbol.upper()}*.csv")) if self.reports_root.exists() else []
        path=next((p for p in candidates if p.exists()),None)
        if path is None: return []
        rows=[]
        with path.open(newline="",encoding="utf-8") as handle:
            for item in csv.DictReader(handle):
                parsed=self._date(item.get("date",item.get("timestamp")))
                if parsed is None or not request.start<=parsed<=request.end: continue
                optional=lambda k: self._num(item.get(k)) if item.get(k) not in (None,"") else None
                rows.append(ReplayFrame(sequence=len(rows)+1,timestamp=parsed,symbol=request.symbol.upper(),
                    close=self._num(item.get("close")),rsi14=optional("rsi14"),atr14=optional("atr14"),
                    call_score=optional("call_score"),put_score=optional("put_score"),
                    signal=item.get("signal"),market_regime=item.get("market_regime")))
        return rows

    def snapshot(self):
        scanner=self.scanner(ScannerQuery())
        importance=self.feature_importance()
        walk=self.walk_forward_runs()
        warnings=[]
        if not scanner: warnings.append("No scanner or signal artifacts found.")
        if not importance: warnings.append("No feature-importance artifacts found.")
        if not walk: warnings.append("No walk-forward artifacts found.")
        return {"generated_at":datetime.now(timezone.utc),"scanner_results":scanner,
                "feature_importance":importance,"walk_forward_runs":walk,"data_warnings":warnings}
