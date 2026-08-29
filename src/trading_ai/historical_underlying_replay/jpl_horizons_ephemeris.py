from __future__ import annotations
import csv, hashlib, io, json, math, time, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

JPL_HORIZONS_API="https://ssd.jpl.nasa.gov/api/horizons.api"
DOCUMENTED_API_VERSION="1.3"
SUPPORTED_OBSERVED_API_VERSIONS={"1.2","1.3"}
HORIZONS_IDS={"SUN":"10","MOON":"301","MERCURY":"199","VENUS":"299","MARS":"499","JUPITER":"599","SATURN":"699"}

def _write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def _load_cached_json(path):
    raw=path.read_text()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned=raw
        while cleaned.endswith("\\n"):
            cleaned=cleaned[:-2]
        cleaned=cleaned.rstrip()
        obj=json.loads(cleaned)
        _write_json_atomic(path,obj)
        return obj


def _norm(x): return x%360.0
def ecliptic_longitude_from_xyz(x,y): return _norm(math.degrees(math.atan2(y,x)))
def _cache_key(body,d): return hashlib.sha256(f"{body}|{d.isoformat()}|12:00|GEOCENTRIC|ECLIPTIC".encode()).hexdigest()[:24]

def _query_params(body,d):
    return {"format":"json","COMMAND":f"'{HORIZONS_IDS[body]}'","OBJ_DATA":"'NO'","MAKE_EPHEM":"'YES'",
      "EPHEM_TYPE":"'VECTORS'","CENTER":"'500@399'","REF_PLANE":"'ECLIPTIC'","REF_SYSTEM":"'ICRF'",
      "OUT_UNITS":"'AU-D'","VEC_TABLE":"'1'","VEC_CORR":"'NONE'","CSV_FORMAT":"'YES'",
      "TIME_TYPE":"'UT'","TLIST":f"'{d.isoformat()} 12:00'","TLIST_TYPE":"'CAL'"}

def _parse_vector_result(result):
    if "$$SOE" not in result or "$$EOE" not in result: raise ValueError("Horizons result missing $$SOE/$$EOE")
    body=result.split("$$SOE",1)[1].split("$$EOE",1)[0]
    for line in [x.strip() for x in body.splitlines() if x.strip()]:
        row=next(csv.reader(io.StringIO(line))); nums=[]
        for field in row:
            try: nums.append(float(field.strip()))
            except Exception: pass
        if len(nums)>=4: return tuple(nums[-3:])
    raise ValueError("Unable to parse Horizons X/Y/Z vector row")

def fetch_geocentric_ecliptic_state(body,d,cache_dir,timeout_seconds=30,request_pause_seconds=.35):
    body=body.upper()
    if body not in HORIZONS_IDS: raise ValueError(f"Unsupported Horizons body: {body}")
    cache_dir.mkdir(parents=True,exist_ok=True)
    cp=cache_dir/f"{d.isoformat()}_{body}_{_cache_key(body,d)}.json"
    if cp.exists():
        out=_load_cached_json(cp); out["cache_mode"]="REUSED"; return out
    url=JPL_HORIZONS_API+"?"+urllib.parse.urlencode(_query_params(body,d))
    req=urllib.request.Request(url,headers={"User-Agent":"TradingPlatform-M77.15-Research/1.0"})
    with urllib.request.urlopen(req,timeout=timeout_seconds) as response:
        payload=json.loads(response.read().decode("utf-8"))
    sig=payload.get("signature") or {}; version=str(sig.get("version") or "")
    if version not in SUPPORTED_OBSERVED_API_VERSIONS:
        raise RuntimeError(
            "JPL Horizons API version unsupported: "
            f"documented={DOCUMENTED_API_VERSION}, observed={version or 'UNKNOWN'}, "
            f"supported={sorted(SUPPORTED_OBSERVED_API_VERSIONS)}"
        )
    result=payload.get("result")
    if not isinstance(result,str): raise RuntimeError("JPL Horizons response missing result")
    x,y,z=_parse_vector_result(result)
    out={"provider":"NASA_JPL_HORIZONS", "api_version_observed":version,
      "api_version_documented":DOCUMENTED_API_VERSION,
      "api_version_compatibility":"SUPPORTED_OBSERVED_VERSION","body":body,"horizons_id":HORIZONS_IDS[body],
      "date":d.isoformat(),"time_utc":"12:00:00","center":"EARTH_GEOCENTER_500@399","reference_plane":"ECLIPTIC",
      "reference_system":"ICRF","vector_correction":"NONE_GEOMETRIC","x_au":x,"y_au":y,"z_au":z,
      "tropical_ecliptic_longitude_deg":ecliptic_longitude_from_xyz(x,y),
      "source_url_sha256":hashlib.sha256(url.encode()).hexdigest(),"cache_mode":"MATERIALIZED"}
    _write_json_atomic(cp,out); time.sleep(request_pause_seconds); return out


def _parse_state_vector_result(result):
    if "$$SOE" not in result or "$$EOE" not in result:
        raise ValueError("Horizons state result missing $$SOE/$$EOE")
    body=result.split("$$SOE",1)[1].split("$$EOE",1)[0]
    for line in [x.strip() for x in body.splitlines() if x.strip()]:
        row=next(csv.reader(io.StringIO(line))); nums=[]
        for field in row:
            try: nums.append(float(field.strip()))
            except Exception: pass
        if len(nums)>=7:
            return tuple(nums[-6:])
    raise ValueError("Unable to parse Horizons X/Y/Z/VX/VY/VZ state row")

def fetch_geocentric_ecliptic_state_vector(body,d,cache_dir,timeout_seconds=30,request_pause_seconds=.35):
    body=body.upper()
    if body not in HORIZONS_IDS:
        raise ValueError(f"Unsupported Horizons body: {body}")
    cache_dir.mkdir(parents=True,exist_ok=True)
    cp=cache_dir/f"{d.isoformat()}_{body}_STATE2_{_cache_key(body,d)}.json"
    if cp.exists():
        out=_load_cached_json(cp); out["cache_mode"]="REUSED"; return out
    q=_query_params(body,d)
    q["VEC_TABLE"]="'2'"
    url=JPL_HORIZONS_API+"?"+urllib.parse.urlencode(q)
    req=urllib.request.Request(url,headers={"User-Agent":"TradingPlatform-M77.15-Research/1.0"})
    with urllib.request.urlopen(req,timeout=timeout_seconds) as response:
        payload=json.loads(response.read().decode("utf-8"))
    sig=payload.get("signature") or {}; version=str(sig.get("version") or "")
    if version not in SUPPORTED_OBSERVED_API_VERSIONS:
        raise RuntimeError(
            "JPL Horizons API version unsupported: "
            f"documented={DOCUMENTED_API_VERSION}, observed={version or 'UNKNOWN'}, "
            f"supported={sorted(SUPPORTED_OBSERVED_API_VERSIONS)}"
        )
    result=payload.get("result")
    if not isinstance(result,str):
        raise RuntimeError("JPL Horizons response missing result")
    x,y,z,vx,vy,vz=_parse_state_vector_result(result)
    out={"provider":"NASA_JPL_HORIZONS","api_version_observed":version,
      "api_version_documented":DOCUMENTED_API_VERSION,"api_version_compatibility":"SUPPORTED_OBSERVED_VERSION",
      "body":body,"horizons_id":HORIZONS_IDS[body],"date":d.isoformat(),"time_utc":"12:00:00",
      "center":"EARTH_GEOCENTER_500@399","reference_plane":"ECLIPTIC","reference_system":"ICRF",
      "vector_correction":"NONE_GEOMETRIC","x_au":x,"y_au":y,"z_au":z,
      "vx_au_per_day":vx,"vy_au_per_day":vy,"vz_au_per_day":vz,
      "source_url_sha256":hashlib.sha256(url.encode()).hexdigest(),"cache_mode":"MATERIALIZED"}
    _write_json_atomic(cp,out); time.sleep(request_pause_seconds); return out


def _observer_query_params(body,d):
    return {
        "format":"json",
        "COMMAND":f"'{HORIZONS_IDS[body]}'",
        "OBJ_DATA":"'NO'",
        "MAKE_EPHEM":"'YES'",
        "EPHEM_TYPE":"'OBSERVER'",
        "CENTER":"'500@399'",
        "REF_SYSTEM":"'ICRF'",
        "CAL_FORMAT":"'CAL'",
        "TIME_DIGITS":"'MINUTES'",
        "ANG_FORMAT":"'DEG'",
        "APPARENT":"'AIRLESS'",
        "CSV_FORMAT":"'YES'",
        "TIME_TYPE":"'UT'",
        "QUANTITIES":"'31'",
        "TLIST":f"'{d.isoformat()} 12:00'",
        "TLIST_TYPE":"'CAL'",
    }

def _parse_observer_ecliptic_result(result):
    if "$$SOE" not in result or "$$EOE" not in result:
        raise ValueError("Horizons observer result missing $$SOE/$$EOE")
    body=result.split("$$SOE",1)[1].split("$$EOE",1)[0]
    for line in [x.strip() for x in body.splitlines() if x.strip()]:
        row=next(csv.reader(io.StringIO(line)))
        numeric=[]
        for field in row:
            try:
                numeric.append(float(field.strip()))
            except Exception:
                continue
        if len(numeric)>=2:
            lon,lat=numeric[-2],numeric[-1]
            if 0.0 <= lon < 360.0 and -90.0 <= lat <= 90.0:
                return lon,lat
    raise ValueError("Unable to parse Horizons apparent observer ecliptic longitude/latitude")

def fetch_geocentric_apparent_ecliptic_longitude(body,d,cache_dir,timeout_seconds=30,request_pause_seconds=.35):
    body=body.upper()
    if body not in HORIZONS_IDS:
        raise ValueError(f"Unsupported Horizons body: {body}")
    cache_dir.mkdir(parents=True,exist_ok=True)
    cp=cache_dir/f"{d.isoformat()}_{body}_APP_ECL31_{_cache_key(body,d)}.json"
    if cp.exists():
        out=_load_cached_json(cp)
        out["cache_mode"]="REUSED"
        return out

    url=JPL_HORIZONS_API+"?"+urllib.parse.urlencode(_observer_query_params(body,d))
    req=urllib.request.Request(url,headers={"User-Agent":"TradingPlatform-M77.15-Research/1.0"})
    with urllib.request.urlopen(req,timeout=timeout_seconds) as response:
        payload=json.loads(response.read().decode("utf-8"))

    sig=payload.get("signature") or {}
    version=str(sig.get("version") or "")
    if version not in SUPPORTED_OBSERVED_API_VERSIONS:
        raise RuntimeError(
            "JPL Horizons API version unsupported: "
            f"documented={DOCUMENTED_API_VERSION}, observed={version or 'UNKNOWN'}, "
            f"supported={sorted(SUPPORTED_OBSERVED_API_VERSIONS)}"
        )

    result=payload.get("result")
    if not isinstance(result,str):
        raise RuntimeError("JPL Horizons response missing result")

    lon,lat=_parse_observer_ecliptic_result(result)
    out={
        "provider":"NASA_JPL_HORIZONS",
        "api_version_observed":version,
        "api_version_documented":DOCUMENTED_API_VERSION,
        "api_version_compatibility":"SUPPORTED_OBSERVED_VERSION",
        "body":body,
        "horizons_id":HORIZONS_IDS[body],
        "date":d.isoformat(),
        "time_utc":"12:00:00",
        "center":"EARTH_GEOCENTER_500@399",
        "ephemeris_type":"OBSERVER",
        "quantity":"31_OBSERVER_ECLIPTIC_LONGITUDE_LATITUDE",
        "apparent":"AIRLESS",
        "observer_ecliptic_longitude_deg":lon,
        "observer_ecliptic_latitude_deg":lat,
        "source_url_sha256":hashlib.sha256(url.encode()).hexdigest(),
        "cache_mode":"MATERIALIZED",
    }
    _write_json_atomic(cp,out)
    time.sleep(request_pause_seconds)
    return out
