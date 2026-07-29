from __future__ import annotations
import json, math, statistics
from collections import Counter
from pathlib import Path
from datetime import date, datetime, timezone
from typing import Any, Iterable
from sqlalchemy import text
from trading_ai.database import SessionLocal
from .contracts import MarketOverviewSnapshot

CASH_INDEXES = {"SPX":"S&P 500 Index", "NDX":"Nasdaq-100 Index", "RUT":"Russell 2000 Index"}
INDEX_PROXIES = {"SPY":"S&P 500 ETF", "QQQ":"Nasdaq-100 ETF", "IWM":"Russell 2000 ETF", "DIA":"Dow Jones ETF"}
INDEX_PROXY_MAP = {"SPX":"SPY", "NDX":"QQQ", "RUT":"IWM"}
INDEX_SYMBOL_ALIASES = {
    "SPX": ("SPX", "I:SPX", "$SPX", "^SPX"),
    "NDX": ("NDX", "I:NDX", "$NDX", "^NDX"),
    "RUT": ("RUT", "I:RUT", "$RUT", "^RUT", "RTY", "I:RTY"),
}
INDEX_ALIAS_TO_CANONICAL = {
    alias.upper(): canonical
    for canonical, aliases in INDEX_SYMBOL_ALIASES.items()
    for alias in aliases
}
INDEXES = {**CASH_INDEXES, **INDEX_PROXIES}
SECTORS = {"XLK":"Technology","XLF":"Financials","XLE":"Energy","XLV":"Health Care","XLI":"Industrials","XLY":"Consumer Discretionary","XLP":"Consumer Staples","XLB":"Materials","XLRE":"Real Estate","XLU":"Utilities","XLC":"Communication Services"}
CROSS_ASSET = {"TLT":"Long Treasuries","IEF":"Intermediate Treasuries","HYG":"High Yield Credit","LQD":"Investment Grade Credit","UUP":"U.S. Dollar","GLD":"Gold","USO":"Oil","RSP":"Equal Weight S&P 500","IWD":"Value","IWF":"Growth"}

def _f(v: Any, default=0.0) -> float:
    try:
        x=float(v); return x if math.isfinite(x) else default
    except (TypeError,ValueError): return default

def _pct_change(values:list[float], periods:int)->float:
    if len(values)<=periods or not values[-periods-1]: return 0.0
    return (values[-1]/values[-periods-1]-1.0)*100.0

def _avg(values:Iterable[float])->float:
    vals=list(values); return sum(vals)/len(vals) if vals else 0.0

def _clamp(x:float, lo=0.0, hi=100.0)->float: return max(lo,min(hi,x))

class MarketOverviewService:
    def __init__(self, session_factory=SessionLocal, root: str | Path = "."):
        self.session_factory = session_factory
        self.root = Path(root)

    def _trend_report(self, filename: str) -> dict[str, Any]:
        path = self.root / "reports" / "trend_intelligence" / filename
        try:
            payload = json.loads(path.read_text())
            return payload if isinstance(payload, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
        return dict(sorted(Counter(str(row.get(key) or "UNAVAILABLE") for row in rows).items()))

    @staticmethod
    def _top_symbols(rows: list[dict[str, Any]], key: str, *, reverse: bool = True, limit: int = 8) -> list[dict[str, Any]]:
        valid = [row for row in rows if row.get("symbol") and row.get(key) is not None]
        valid.sort(key=lambda row: _f(row.get(key)), reverse=reverse)
        return [
            {
                "symbol": row.get("symbol"),
                "score": _f(row.get(key)),
                "state": row.get("trend_stage") or row.get("transition_state") or row.get("forecast_direction") or row.get("participation_state"),
                "as_of_date": row.get("as_of_date"),
            }
            for row in valid[:limit]
        ]

    def trend_intelligence_summary(self) -> dict[str, Any]:
        base = self._trend_report("latest.json")
        transitions = self._trend_report("transitions_latest.json")
        forecasts = self._trend_report("forecasts_latest.json")
        institutional = self._trend_report("institutional_latest.json")
        operations = self._trend_report("phase6_latest.json")

        base_rows = list(base.get("results") or [])
        transition_rows = list(transitions.get("results") or [])
        forecast_rows = list(forecasts.get("results") or [])
        institutional_rows = list(institutional.get("results") or [])

        preferred_forecasts: dict[str, dict[str, Any]] = {}
        for row in forecast_rows:
            symbol = str(row.get("symbol") or "")
            horizon = int(row.get("horizon_days") or 0)
            current = preferred_forecasts.get(symbol)
            if current is None or abs(horizon - 10) < abs(int(current.get("horizon_days") or 0) - 10):
                preferred_forecasts[symbol] = row
        forecast_view = list(preferred_forecasts.values())

        base_by_symbol = {str(row.get("symbol")): row for row in base_rows}
        transition_by_symbol = {str(row.get("symbol")): row for row in transition_rows}
        institutional_by_symbol = {str(row.get("symbol")): row for row in institutional_rows}
        symbol_rows: list[dict[str, Any]] = []
        for symbol in sorted(set(base_by_symbol) | set(transition_by_symbol) | set(preferred_forecasts) | set(institutional_by_symbol)):
            b = base_by_symbol.get(symbol, {})
            t = transition_by_symbol.get(symbol, {})
            f = preferred_forecasts.get(symbol, {})
            i = institutional_by_symbol.get(symbol, {})
            symbol_rows.append({
                "symbol": symbol,
                "as_of_date": b.get("as_of_date") or t.get("as_of_date") or f.get("as_of_date") or i.get("as_of_date"),
                "base_trend": b.get("intermediate_term") or b.get("short_term") or "UNAVAILABLE",
                "trend_stage": b.get("trend_stage", "UNAVAILABLE"),
                "trend_alignment_score": _f(b.get("alignment_score"), 50.0),
                "trend_quality_score": _f(b.get("trend_quality_score"), 50.0),
                "transition_state": t.get("transition_state", "UNAVAILABLE"),
                "breakout_state": t.get("breakout_state", "UNAVAILABLE"),
                "reversal_risk_score": _f(t.get("reversal_risk_score")),
                "exhaustion_risk_score": _f(t.get("exhaustion_risk_score")),
                "forecast_direction": f.get("forecast_direction", "UNAVAILABLE"),
                "forecast_confidence_score": _f(f.get("confidence_score")),
                "institutional_participation_score": _f(i.get("participation_score"), 50.0),
                "institutional_participation_state": i.get("participation_state", "UNAVAILABLE"),
                "deterioration_risk_score": _f(i.get("deterioration_risk_score"), 50.0),
            })

        bullish = sum(1 for row in base_rows if "BULL" in str(row.get("intermediate_term") or row.get("short_term") or ""))
        bearish = sum(1 for row in base_rows if "BEAR" in str(row.get("intermediate_term") or row.get("short_term") or ""))
        neutral = max(0, len(base_rows) - bullish - bearish)
        transition_watch = sum(
            1 for row in transition_rows
            if str(row.get("transition_state")) not in {"CONTINUATION", "IN_TREND", "UNAVAILABLE"}
            or _f(row.get("reversal_risk_score")) >= 60
            or _f(row.get("exhaustion_risk_score")) >= 60
        )

        available = any((base_rows, transition_rows, forecast_rows, institutional_rows, operations))
        component_status = {
            "base": base.get("status", "NOT_AVAILABLE"),
            "transition": transitions.get("status", "NOT_AVAILABLE"),
            "forecast": forecasts.get("status", "NOT_AVAILABLE"),
            "institutional": institutional.get("status", "NOT_AVAILABLE"),
            "operations": operations.get("status", "NOT_AVAILABLE"),
        }
        statuses = set(component_status.values())
        status = "NOT_AVAILABLE" if not available else ("FAILED" if "FAILED" in statuses else "PARTIAL" if "NOT_AVAILABLE" in statuses or "DEGRADED" in statuses else "READY")

        return {
            "schema_version": "m53.trend-intelligence-ui.v1",
            "status": status,
            "snapshot_timestamp": max(
                [str(value) for value in [
                    base.get("snapshot_timestamp"),
                    transitions.get("snapshot_timestamp"),
                    forecasts.get("snapshot_timestamp"),
                    institutional.get("snapshot_timestamp"),
                    operations.get("snapshot_timestamp"),
                ] if value],
                default=None,
            ),
            "symbol_count": len(symbol_rows),
            "component_status": component_status,
            "breadth": {
                "bullish": bullish,
                "neutral": neutral,
                "bearish": bearish,
                "bullish_pct": (100.0 * bullish / len(base_rows)) if base_rows else 0.0,
                "bearish_pct": (100.0 * bearish / len(base_rows)) if base_rows else 0.0,
                "transition_watch_count": transition_watch,
            },
            "distributions": {
                "base_trend": self._distribution(base_rows, "intermediate_term"),
                "trend_stage": self._distribution(base_rows, "trend_stage"),
                "transition": self._distribution(transition_rows, "transition_state"),
                "breakout": self._distribution(transition_rows, "breakout_state"),
                "forecast": self._distribution(forecast_view, "forecast_direction"),
                "institutional_participation": self._distribution(institutional_rows, "participation_state"),
                "institutional_leadership": self._distribution(institutional_rows, "leadership_state"),
                "institutional_deterioration": self._distribution(institutional_rows, "deterioration_state"),
            },
            "top_strengthening": self._top_symbols(base_rows, "alignment_score", reverse=True),
            "top_deteriorating": self._top_symbols(institutional_rows, "deterioration_risk_score", reverse=True),
            "top_reversal_risk": self._top_symbols(transition_rows, "reversal_risk_score", reverse=True),
            "top_forecast_confidence": self._top_symbols(forecast_view, "confidence_score", reverse=True),
            "institutional_overview": institutional.get("market_overview") or {},
            "operations": operations or {
                "status": "NOT_AVAILABLE",
                "score": 0.0,
                "assessments": {},
                "milestone_52_closure_eligible": False,
            },
            "symbols": symbol_rows,
            "warnings": [
                message for message in [
                    "Base trend intelligence is unavailable." if not base_rows else "",
                    "Transition intelligence is unavailable." if not transition_rows else "",
                    "Forecast intelligence is unavailable." if not forecast_rows else "",
                    "Institutional trend intelligence is unavailable." if not institutional_rows else "",
                    "Phase 6 operational scorecard is unavailable." if not operations else "",
                ] if message
            ],
        }

    def enrich_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(payload or {})
        enriched["trend_intelligence"] = self.trend_intelligence_summary()
        return enriched

    def _series(self, session, symbols:list[str], limit=220)->dict[str,list[dict[str,Any]]]:
        rows=session.execute(text("""
            SELECT symbol,date,open,high,low,close,volume FROM (
              SELECT symbol,date,open,high,low,close,volume,
                     row_number() over(partition by symbol order by date desc) rn
              FROM price_history WHERE symbol = ANY(:symbols)
            ) q WHERE rn <= :limit ORDER BY symbol,date
        """),{"symbols":symbols,"limit":limit}).mappings().all()
        out={s:[] for s in symbols}
        for r in rows: out.setdefault(r["symbol"],[]).append(dict(r))
        return out

    @staticmethod
    def _canonical_dealer_symbol(symbol: Any) -> str:
        normalized = str(symbol or "").strip().upper()
        return INDEX_ALIAS_TO_CANONICAL.get(normalized, normalized)

    def _dealer(self, session, symbols:list[str])->dict[str,dict[str,Any]]:
        requested = [self._canonical_dealer_symbol(symbol) for symbol in symbols]
        query_symbols: list[str] = []
        for symbol in requested:
            query_symbols.extend(INDEX_SYMBOL_ALIASES.get(symbol, (symbol,)))
        query_symbols = list(dict.fromkeys(value.upper() for value in query_symbols if value))
        try:
            rows=session.execute(text("""
              SELECT symbol,as_of_date,quote_date,spot_price,gamma_regime,gamma_flip,
                primary_call_wall,primary_put_wall,magnet_strike,expected_move_pct,atm_iv,iv_term_slope,
                put_skew,call_skew,institutional_positioning_score,positioning_label,bull_probability,
                bear_probability,range_probability,breakout_probability,breakdown_probability,
                volatility_expansion_probability,volatility_compression_probability,confidence_score,
                net_gamma_exposure,net_delta_exposure,net_vanna_exposure,net_charm_exposure,quote_coverage_pct
              FROM dealer_position_snapshot
              WHERE upper(symbol) = ANY(:symbols)
              ORDER BY as_of_date DESC, quote_date DESC NULLS LAST
            """),{"symbols":query_symbols}).mappings().all()
            resolved: dict[str, dict[str, Any]] = {}
            for row in rows:
                raw_symbol = str(row["symbol"]).strip().upper()
                canonical_symbol = self._canonical_dealer_symbol(raw_symbol)
                if canonical_symbol not in requested or canonical_symbol in resolved:
                    continue
                payload = dict(row)
                payload["source_symbol"] = raw_symbol
                payload["symbol"] = canonical_symbol
                resolved[canonical_symbol] = payload
            return resolved
        except Exception:
            session.rollback(); return {}

    def _metrics(self, rows:list[dict[str,Any]], *, volume_applicable: bool = True)->dict[str,Any]:
        closes=[_f(r["close"]) for r in rows if _f(r["close"])>0]; vols=[_f(r["volume"]) for r in rows[-20:]] if volume_applicable else []
        if len(closes)<2: return {"available":False}
        sma=lambda n:_avg(closes[-n:]) if len(closes)>=n else _avg(closes)
        daily=[closes[i]/closes[i-1]-1 for i in range(1,len(closes)) if closes[i-1]]
        rv20=statistics.pstdev(daily[-20:])*math.sqrt(252)*100 if len(daily)>=2 else 0
        latest=closes[-1]
        return {"available":True,"close":latest,"return_1d":_pct_change(closes,1),"return_5d":_pct_change(closes,5),"return_20d":_pct_change(closes,20),"sma20":sma(20),"sma50":sma(50),"sma200":sma(200),"above_20":latest>sma(20),"above_50":latest>sma(50),"above_200":latest>sma(200),"new_high_20":latest>=max(closes[-20:]),"new_low_20":latest<=min(closes[-20:]),"realized_vol_20d":rv20,"relative_volume":(_avg(vols[-3:])/_avg(vols) if _avg(vols) else None),"latest_volume":vols[-1] if vols else None,"volume_applicable":volume_applicable,"previous_close":closes[-2]}

    def build(self, universe_name="canonical", persist=True)->MarketOverviewSnapshot:
        now=datetime.now(timezone.utc)
        with self.session_factory() as session:
            universe=[r[0] for r in session.execute(text("SELECT DISTINCT symbol FROM price_history")).all()]
            breadth_universe=[s for s in universe if s not in CASH_INDEXES]
            all_symbols=sorted(set(universe)|set(INDEXES)|set(SECTORS)|set(CROSS_ASSET))
            series=self._series(session,all_symbols)
            metrics={s:self._metrics(rows, volume_applicable=s not in CASH_INDEXES) for s,rows in series.items()}
            valid={s:m for s,m in metrics.items() if m.get("available")}
            evaluated=len([s for s in breadth_universe if s in valid]); adv=sum(valid[s]["return_1d"]>0 for s in breadth_universe if s in valid); dec=sum(valid[s]["return_1d"]<0 for s in breadth_universe if s in valid); unchanged=max(0,evaluated-adv-dec)
            pct20=100*_avg(float(valid[s]["above_20"]) for s in breadth_universe if s in valid); pct50=100*_avg(float(valid[s]["above_50"]) for s in breadth_universe if s in valid); pct200=100*_avg(float(valid[s]["above_200"]) for s in breadth_universe if s in valid)
            highs=sum(valid[s]["new_high_20"] for s in breadth_universe if s in valid); lows=sum(valid[s]["new_low_20"] for s in breadth_universe if s in valid)
            upvol=sum(valid[s]["latest_volume"] for s in breadth_universe if s in valid and valid[s]["return_1d"]>0); downvol=sum(valid[s]["latest_volume"] for s in breadth_universe if s in valid and valid[s]["return_1d"]<0)
            ad_ratio=adv/max(dec,1); volume_ratio=upvol/max(downvol,1)
            breadth_score=_clamp(.28*pct20+.27*pct50+.20*pct200+15*min(ad_ratio,2)/2+10*min(volume_ratio,2)/2)
            breadth_regime="HEALTHY_BROAD" if breadth_score>=70 else "HEALTHY_NARROW" if breadth_score>=58 else "DIVERGING" if breadth_score>=45 else "DETERIORATING" if breadth_score>=28 else "CAPITULATION"
            index_context=[]
            for sym,name in CASH_INDEXES.items():
                m=valid.get(sym,{})
                proxy=INDEX_PROXY_MAP[sym]
                proxy_metrics=valid.get(proxy,{})
                index_context.append({
                    "symbol":sym,"name":name,"asset_type":"CASH_INDEX","benchmark_family":sym,
                    "proxy_symbol":proxy,
                    "proxy_return_spread_1d":m.get("return_1d",0)-proxy_metrics.get("return_1d",0) if m and proxy_metrics else None,
                    "proxy_return_spread_20d":m.get("return_20d",0)-proxy_metrics.get("return_20d",0) if m and proxy_metrics else None,
                    **m,
                })
            for sym,name in INDEX_PROXIES.items():
                m=valid.get(sym,{})
                family=next((idx for idx,proxy in INDEX_PROXY_MAP.items() if proxy==sym), sym)
                index_context.append({"symbol":sym,"name":name,"asset_type":"ETF_PROXY","benchmark_family":family,**m})
            benchmark_symbols=[s for s in CASH_INDEXES if s in valid] or [s for s in INDEX_PROXIES if s in valid]
            index_trend=_avg((75 if valid[s].get("above_20") and valid[s].get("above_50") else 55 if valid[s].get("above_50") else 30) for s in benchmark_symbols)
            momentum=_clamp(50+_avg(valid[s].get("return_20d",0) for s in benchmark_symbols)*3)
            trend_score=_clamp(.55*index_trend+.45*(.45*pct20+.35*pct50+.20*pct200))
            dealer=self._dealer(session,list(CASH_INDEXES)+list(INDEX_PROXIES)+list(SECTORS))
            dealer_rows=[]
            for sym in list(CASH_INDEXES)+list(INDEX_PROXIES)+list(SECTORS):
                d=dealer.get(sym)
                if d:
                    dealer_rows.append({k:(v.isoformat() if isinstance(v,date) else v) for k,v in d.items()})
            atm_ivs=[_f(d.get("atm_iv"))*100 if _f(d.get("atm_iv"))<3 else _f(d.get("atm_iv")) for d in dealer.values() if d.get("atm_iv") is not None]
            realized=[valid[s]["realized_vol_20d"] for s in benchmark_symbols if s in valid]
            avg_iv=_avg(atm_ivs); avg_rv=_avg(realized); vrp=avg_iv-avg_rv
            vol_score=_clamp(50-vrp*1.5)
            volatility_regime="EXPANDING" if _avg(_f(d.get("volatility_expansion_probability")) for d in dealer.values())>.58 else "COMPRESSED" if vrp>5 else "NORMAL"
            sector_rows=[]; spy20=valid.get("SPY",{}).get("return_20d",0)
            for sym,name in SECTORS.items():
                m=valid.get(sym)
                if not m: continue
                rs=m["return_20d"]-spy20; score=_clamp(50+rs*4+m["return_5d"]*2)
                label="LEADING" if score>=65 else "IMPROVING" if score>=52 else "WEAKENING" if score>=40 else "LAGGING"
                d=dealer.get(sym,{})
                sector_rows.append({"sector":name,"sector_etf":sym,"return_1d":m["return_1d"],"return_5d":m["return_5d"],"return_20d":m["return_20d"],"relative_strength":rs,"trend_score":_clamp(50+(10 if m["above_20"] else -10)+(15 if m["above_50"] else -15)+(20 if m["above_200"] else -20)),"momentum_score":score,"dealer_positioning_score":d.get("institutional_positioning_score"),"rotation_label":label})
            sector_rows.sort(key=lambda x:x["momentum_score"],reverse=True)
            cross=[]
            for sym,name in CROSS_ASSET.items():
                if sym in valid: cross.append({"symbol":sym,"name":name,"return_1d":valid[sym]["return_1d"],"return_5d":valid[sym]["return_5d"],"return_20d":valid[sym]["return_20d"],"trend":"UP" if valid[sym]["above_50"] else "DOWN"})
            credit=next((x for x in cross if x["symbol"]=="HYG"),{}); bonds=next((x for x in cross if x["symbol"]=="TLT"),{})
            risk_on=_clamp(.45*trend_score+.35*breadth_score+.20*(50+_f(credit.get("return_20d"))*4-_f(bonds.get("return_20d"))*2))
            sentiment=_clamp(.55*risk_on+.45*(100-vol_score))
            health=_clamp(.35*breadth_score+.30*trend_score+.15*momentum+.10*risk_on+.10*(100-abs(vrp)*2))
            market_bias="STRONGLY_BULLISH" if health>=75 and trend_score>=70 else "MODERATELY_BULLISH" if health>=60 else "NEUTRAL" if health>=45 else "MODERATELY_BEARISH" if health>=30 else "STRONGLY_BEARISH"
            trend_regime="STRONG_UPTREND" if trend_score>=75 else "UPTREND" if trend_score>=60 else "RANGE" if trend_score>=42 else "DOWNTREND" if trend_score>=25 else "STRONG_DOWNTREND"
            liquidity_ratio=_avg(valid[s].get("relative_volume",0) or 0 for s in breadth_universe if s in valid and valid[s].get("volume_applicable",True)); liquidity_regime="DEEP" if liquidity_ratio>=1.25 else "NORMAL" if liquidity_ratio>=.75 else "THIN"
            correlation_regime="CONCENTRATED" if breadth_score<50 and trend_score>60 else "NORMAL"
            transition="HIGH" if abs(trend_score-breadth_score)>25 or breadth_regime in {"DIVERGING","DETERIORATING"} else "MODERATE" if abs(trend_score-breadth_score)>15 else "LOW"
            preferred="LONG_PREMIUM_FAVORABLE" if volatility_regime=="EXPANDING" and trend_score>=55 else "SHORT_PREMIUM_FAVORABLE" if volatility_regime=="COMPRESSED" and breadth_regime.startswith("HEALTHY") else "SELECTIVE_DIRECTIONAL_SPREADS" if market_bias!="NEUTRAL" else "NEUTRAL_DEFINED_RISK"
            alerts=[]
            def alert(severity,title,evidence,implication): alerts.append({"severity":severity,"title":title,"evidence":evidence,"trading_implication":implication})
            if breadth_regime in {"DIVERGING","DETERIORATING"}: alert("HIGH","Breadth deterioration",f"Breadth score {breadth_score:.1f}; {adv} advancers versus {dec} decliners.","Reduce directional conviction and favor defined-risk structures.")
            if transition!="LOW": alert("MEDIUM","Regime transition risk",f"Trend/breadth divergence is {abs(trend_score-breadth_score):.1f} points.","Use smaller size and require confirmation.")
            neg_gamma=[d for d in dealer_rows if d.get("gamma_regime")=="NEGATIVE_GAMMA"]
            if neg_gamma: alert("HIGH","Negative gamma exposure",", ".join(d["symbol"] for d in neg_gamma),"Expect wider intraday ranges and faster hedging feedback.")
            if liquidity_regime=="THIN": alert("MEDIUM","Thin participation",f"Relative-volume composite {liquidity_ratio:.2f}.","Tighten liquidity filters and reduce size.")
            cash_index_rows=[row for row in index_context if row.get("asset_type")=="CASH_INDEX" and row.get("available")]
            strongest_cash_index=max(cash_index_rows,key=lambda x:_f(x.get("return_20d")),default=None)
            weakest_cash_index=min(cash_index_rows,key=lambda x:_f(x.get("return_20d")),default=None)
            opportunity={"best_bullish_sector":sector_rows[0] if sector_rows else None,"best_bearish_sector":sector_rows[-1] if sector_rows else None,"best_breakout_market":max(dealer_rows,key=lambda x:_f(x.get("breakout_probability")),default=None),"best_range_market":max(dealer_rows,key=lambda x:_f(x.get("range_probability")),default=None),"strongest_cash_index":strongest_cash_index,"weakest_cash_index":weakest_cash_index,"long_premium_fit":preferred if "LONG_PREMIUM" in preferred else None,"short_premium_fit":preferred if "SHORT_PREMIUM" in preferred else None}
            asof=max((rows[-1]["date"] for rows in series.values() if rows),default=now.date())
            snap=MarketOverviewSnapshot(now,str(asof),market_bias,preferred,health,trend_score,momentum,breadth_score,risk_on,sentiment,_clamp(70+min(evaluated,500)/500*20-len(alerts)*2),trend_regime,volatility_regime,breadth_regime,liquidity_regime,correlation_regime,transition,index_context,{"universe":universe_name,"excluded_cash_indices":sorted(CASH_INDEXES),"evaluated_symbols":evaluated,"advancers":adv,"decliners":dec,"unchanged":unchanged,"advance_decline_ratio":ad_ratio,"pct_above_ema20":pct20,"pct_above_sma50":pct50,"pct_above_sma200":pct200,"new_highs_20d":highs,"new_lows_20d":lows,"up_volume":upvol,"down_volume":downvol,"up_down_volume_ratio":volume_ratio,"breadth_score":breadth_score,"breadth_regime":breadth_regime},{"short_term_score":momentum,"intermediate_term_score":trend_score,"long_term_score":pct200,"trend_regime":trend_regime},{"risk_on_score":risk_on,"sentiment_score":sentiment,"trend_regime":trend_regime,"volatility_regime":volatility_regime,"breadth_regime":breadth_regime,"liquidity_regime":liquidity_regime,"correlation_regime":correlation_regime,"regime_transition_risk":transition},sector_rows,dealer_rows,{"average_atm_iv":avg_iv,"average_realized_volatility_20d":avg_rv,"volatility_risk_premium":vrp,"volatility_regime":volatility_regime,"long_premium_attractiveness":_clamp(50-vrp*3+(_avg(_f(d.get("volatility_expansion_probability")) for d in dealer.values())-.5)*50),"short_premium_attractiveness":_clamp(50+vrp*3+(_avg(_f(d.get("range_probability")) for d in dealer.values())-.5)*50)},{"evaluated_symbols":evaluated,"relative_volume_composite":liquidity_ratio,"liquidity_regime":liquidity_regime,"advance_decline_ratio":ad_ratio,"up_down_volume_ratio":volume_ratio},cross,alerts,opportunity,{"price_history_as_of":str(asof),"dealer_snapshot_as_of":max((str(d.get("as_of_date")) for d in dealer.values()),default=None),"cash_indices_as_of":max((str(series[s][-1]["date"]) for s in CASH_INDEXES if series.get(s)),default=None),"generated_at":now.isoformat(),"source":"PostgreSQL"},["Dealer positioning is an OI-and-Greeks proxy, not observed dealer inventory."])
            snap.trend_intelligence = self.trend_intelligence_summary()
            if persist: self.persist(session,snap)
            return snap

    def persist(self,session,snapshot:MarketOverviewSnapshot)->None:
        p=snapshot.to_dict(); ts=snapshot.snapshot_timestamp; asof=date.fromisoformat(snapshot.as_of_date)
        session.execute(text("""INSERT INTO market_overview_snapshot(snapshot_timestamp,as_of_date,market_bias,preferred_strategy,market_health_score,trend_score,momentum_score,breadth_score,risk_on_score,sentiment_score,confidence_score,trend_regime,volatility_regime,breadth_regime,liquidity_regime,correlation_regime,regime_transition_risk,payload_json) VALUES (:ts,:d,:bias,:strategy,:health,:trend,:momentum,:breadth,:risk,:sentiment,:confidence,:tr,:vr,:br,:lr,:cr,:rr,:payload)"""),{"ts":ts,"d":asof,"bias":snapshot.market_bias,"strategy":snapshot.preferred_strategy,"health":snapshot.market_health_score,"trend":snapshot.trend_score,"momentum":snapshot.momentum_score,"breadth":snapshot.breadth_score,"risk":snapshot.risk_on_score,"sentiment":snapshot.sentiment_score,"confidence":snapshot.confidence_score,"tr":snapshot.trend_regime,"vr":snapshot.volatility_regime,"br":snapshot.breadth_regime,"lr":snapshot.liquidity_regime,"cr":snapshot.correlation_regime,"rr":snapshot.regime_transition_risk,"payload":json.dumps(p,default=str)})
        b=snapshot.breadth
        session.execute(text("""INSERT INTO market_breadth_snapshot(snapshot_timestamp,universe_name,as_of_date,evaluated_symbols,advancers,decliners,unchanged,pct_above_ema20,pct_above_sma50,pct_above_sma200,new_highs_20d,new_lows_20d,up_volume,down_volume,breadth_score,breadth_regime,payload_json) VALUES (:ts,:u,:d,:n,:a,:de,:un,:p20,:p50,:p200,:nh,:nl,:uv,:dv,:bs,:br,:payload)"""),{"ts":ts,"u":b["universe"],"d":asof,"n":b["evaluated_symbols"],"a":b["advancers"],"de":b["decliners"],"un":b["unchanged"],"p20":b["pct_above_ema20"],"p50":b["pct_above_sma50"],"p200":b["pct_above_sma200"],"nh":b["new_highs_20d"],"nl":b["new_lows_20d"],"uv":b["up_volume"],"dv":b["down_volume"],"bs":b["breadth_score"],"br":b["breadth_regime"],"payload":json.dumps(b,default=str)})
        for s in snapshot.sectors:
            session.execute(text("""INSERT INTO sector_rotation_snapshot(snapshot_timestamp,sector_etf,as_of_date,sector,return_1d,return_5d,return_20d,relative_strength,trend_score,momentum_score,dealer_positioning_score,rotation_label,payload_json) VALUES (:ts,:etf,:d,:sector,:r1,:r5,:r20,:rs,:trend,:mom,:dealer,:label,:payload)"""),{"ts":ts,"etf":s["sector_etf"],"d":asof,"sector":s["sector"],"r1":s["return_1d"],"r5":s["return_5d"],"r20":s["return_20d"],"rs":s["relative_strength"],"trend":s["trend_score"],"mom":s["momentum_score"],"dealer":s.get("dealer_positioning_score"),"label":s["rotation_label"],"payload":json.dumps(s,default=str)})
        session.commit()

    def latest(self, refresh_if_missing=True)->dict[str,Any]:
        with self.session_factory() as session:
            try:
                row=session.execute(text("SELECT payload_json FROM market_overview_snapshot ORDER BY snapshot_timestamp DESC LIMIT 1")).scalar_one_or_none()
                if row: return self.enrich_payload(json.loads(row))
            except Exception: session.rollback()
        return self.enrich_payload(self.build(persist=False).to_dict()) if refresh_if_missing else {}

    def scanner_context(self)->dict[str,Any]:
        p=self.latest()
        return {"market_bias":p.get("market_bias"),"preferred_strategy":p.get("preferred_strategy"),"market_health_score":p.get("market_health_score",50),"trend_score":p.get("trend_score",50),"breadth_score":p.get("breadth_score",50),"volatility_regime":p.get("volatility_regime"),"regime_transition_risk":p.get("regime_transition_risk"),"sectors":{x["sector_etf"]:x for x in p.get("sectors",[])},"trend_intelligence":p.get("trend_intelligence",{})}
