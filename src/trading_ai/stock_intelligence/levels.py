from __future__ import annotations

from .profile import *
from .multi_timeframe import _rows, _atr

_TIMEFRAME_PRIORITY = {
    "1mo": 70, "1w": 60, "1d": 50, "4h": 40, "2h": 35,
    "1h": 30, "30m": 20, "15m": 15, "5m": 10, "1m": 5,
}

def _unique_timeframes(values):
    unique = {str(value).strip() for value in values if str(value).strip()}
    return sorted(unique, key=lambda value: (-_TIMEFRAME_PRIORITY.get(value, 0), value))

def _primary_timeframe(values, fallback="1d"):
    ordered = _unique_timeframes(values)
    return ordered[0] if ordered else fallback

def _level_timeframes(level):
    values = list(getattr(level, "contributing_timeframes", []) or [])
    values.extend(str(getattr(level, "timeframe", "")).split(","))
    return _unique_timeframes(values)

class SupportResistanceEngine:
    def analyze(self, timeframe, data):
        rows = _rows(data); n = len(rows)
        if n < 20: return [], []
        atr = max(_atr(rows), 1e-9); candidates = []
        for i in range(2, n - 2):
            h = float(rows[i]["high"]); l = float(rows[i]["low"])
            if h >= max(float(x["high"]) for x in rows[i-2:i+3]): candidates.append(("RESISTANCE", h, i))
            if l <= min(float(x["low"]) for x in rows[i-2:i+3]): candidates.append(("SUPPORT", l, i))
        for w in (20, 50, 100):
            if n >= w:
                candidates += [("RESISTANCE", max(float(x["high"]) for x in rows[-w:]), n-1), ("SUPPORT", min(float(x["low"]) for x in rows[-w:]), n-1)]
        out = []
        for typ, price, idx in candidates:
            found = next((x for x in out if x.level_type == typ and abs(x.price-price) <= atr*.35), None)
            if found:
                found.price = (found.price*found.touch_count + price)/(found.touch_count+1)
                found.touch_count += 1; found.strength = min(100, found.strength+8); found.confluence_score = min(100, found.confluence_score+10)
            else:
                age = n-1-idx; strength = max(25, 80-age*.8)
                out.append(PriceLevel(typ, round(price,4), timeframe, round(strength,2), round(strength*.75,2), 1, min(.9,.45+strength/220), max(.1,.55-strength/220), {"age_bars":age}, [timeframe]))
        out.sort(key=lambda x:(-x.strength,x.price))
        return [x for x in out if x.level_type=="SUPPORT"][:12], [x for x in out if x.level_type=="RESISTANCE"][:12]

class SupplyDemandEngine:
    def analyze(self, timeframe, data, supports=None, resistances=None):
        rows = _rows(data); zones = []
        if len(rows) < 12: return zones
        atr = max(_atr(rows), 1e-9)
        for i in range(3, len(rows)-3):
            base = rows[i-2:i+1]; width = max(float(x["high"]) for x in base)-min(float(x["low"]) for x in base)
            move = float(rows[i+3]["close"])-float(rows[i]["close"])
            if width <= atr*1.2 and abs(move) >= atr*1.3:
                typ = "DEMAND" if move > 0 else "SUPPLY"; lo = min(float(x["low"]) for x in base); hi = max(float(x["high"]) for x in base)
                tests = sum(1 for x in rows[i+4:] if float(x["low"]) <= hi and float(x["high"]) >= lo)
                zones.append(PriceZone(typ, round(lo,4), round(hi,4), timeframe, round(min(100,55+abs(move)/atr*12),2), "FRESH" if tests==0 else "TESTED" if tests<3 else "STALE", tests, {"displacement_atr":abs(move)/atr}, [timeframe]))
        if not zones:
            for x in (supports or [])[:3]: zones.append(PriceZone("DEMAND",x.price-atr*.2,x.price+atr*.2,timeframe,x.strength*.8,"STRUCTURAL",x.touch_count,{},[timeframe]))
            for x in (resistances or [])[:3]: zones.append(PriceZone("SUPPLY",x.price-atr*.2,x.price+atr*.2,timeframe,x.strength*.8,"STRUCTURAL",x.touch_count,{},[timeframe]))
        return sorted(zones,key=lambda z:-z.strength)[:12]

class LevelIntelligenceService:
    def __init__(self): self.sr=SupportResistanceEngine(); self.sd=SupplyDemandEngine()
    def analyze(self, data_by_timeframe):
        sup=[]; res=[]; dem=[]; supply=[]
        for tf,data in data_by_timeframe.items():
            s,r=self.sr.analyze(tf,data); z=self.sd.analyze(tf,data,s,r); sup+=s; res+=r; dem += [x for x in z if x.zone_type=="DEMAND"]; supply += [x for x in z if x.zone_type=="SUPPLY"]
        def merge(levels):
            levels=sorted(levels,key=lambda x:x.price); out=[]
            for x in levels:
                x.contributing_timeframes = _level_timeframes(x)
                x.timeframe = _primary_timeframe(x.contributing_timeframes, x.timeframe)
                y=next((z for z in out if abs(z.price-x.price)/max(1,x.price)<.003),None)
                if y:
                    y.strength=min(100,(y.strength+x.strength)/2+10); y.confluence_score=min(100,y.confluence_score+x.confluence_score/2); y.touch_count+=x.touch_count
                    y.contributing_timeframes = _unique_timeframes(_level_timeframes(y)+_level_timeframes(x))
                    y.timeframe = _primary_timeframe(y.contributing_timeframes, y.timeframe)
                else: out.append(x)
            return sorted(out,key=lambda x:-x.strength)
        return {"support_levels":merge(sup),"resistance_levels":merge(res),"demand_zones":sorted(dem,key=lambda x:-x.strength),"supply_zones":sorted(supply,key=lambda x:-x.strength)}
