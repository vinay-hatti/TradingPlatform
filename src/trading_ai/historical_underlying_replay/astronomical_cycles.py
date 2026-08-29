from __future__ import annotations
import math
from datetime import date, datetime, timezone

SYNODIC_MONTH=29.530588853
NEW_MOON_EPOCH=datetime(2000,1,6,18,14,tzinfo=timezone.utc)
FROZEN_HYPOTHESES={
"NEW_MOON_WINDOW":{"family":"LUNAR"},"FULL_MOON_WINDOW":{"family":"LUNAR"},
"FIRST_QUARTER_WINDOW":{"family":"LUNAR"},"LAST_QUARTER_WINDOW":{"family":"LUNAR"},
"MERCURY_RETROGRADE":{"family":"TRADITIONAL"},
"JUPITER_SATURN_CONJUNCTION":{"family":"TRADITIONAL"},
"JUPITER_SATURN_OPPOSITION":{"family":"TRADITIONAL"},
"JUPITER_SATURN_SQUARE":{"family":"TRADITIONAL"},
"JUPITER_SATURN_TRINE":{"family":"TRADITIONAL"},
"MARS_JUPITER_CONJUNCTION":{"family":"TRADITIONAL"},
"MARS_JUPITER_OPPOSITION":{"family":"TRADITIONAL"},
"MARS_JUPITER_SQUARE":{"family":"TRADITIONAL"}}

def norm(x): return x%360.0
def adist(a,b):
    d=abs(norm(a)-norm(b))%360
    return min(d,360-d)
def lunar_phase_angle(d):
    dt=datetime(d.year,d.month,d.day,12,tzinfo=timezone.utc)
    days=(dt-NEW_MOON_EPOCH).total_seconds()/86400
    return norm((days%SYNODIC_MONTH)/SYNODIC_MONTH*360)
def lunar_illumination(d):
    return (1-math.cos(math.radians(lunar_phase_angle(d))))/2

# Low-precision orbital elements: exploratory only, never promotable without
# independent ephemeris parity. Values are deterministic and frozen.
EL={
"mercury":((48.3313,3.24587E-5),(7.0047,5E-8),(29.1241,1.01444E-5),(.387098,0),(.205635,5.59E-10),(168.6562,4.0923344368)),
"earth":((0,0),(0,0),(282.9404,4.70935E-5),(1,0),(.016709,-1.151E-9),(356.0470,.9856002585)),
"mars":((49.5574,2.11081E-5),(1.8497,-1.78E-8),(286.5016,2.92961E-5),(1.523688,0),(.093405,2.516E-9),(18.6021,.5240207766)),
"jupiter":((100.4542,2.76854E-5),(1.3030,-1.557E-7),(273.8777,1.64505E-5),(5.20256,0),(.048498,4.469E-9),(19.8950,.0830853001)),
"saturn":((113.6634,2.38980E-5),(2.4886,-1.081E-7),(339.3939,2.97661E-5),(9.55475,0),(.055546,-9.499E-9),(316.9670,.0334442282))}

def days(d):
    return (datetime(d.year,d.month,d.day,tzinfo=timezone.utc)-datetime(2000,1,1,tzinfo=timezone.utc)).total_seconds()/86400+1.5
def xyz(name,d):
    dd=days(d); e=EL[name]
    N=norm(e[0][0]+e[0][1]*dd); inc=e[1][0]+e[1][1]*dd; w=norm(e[2][0]+e[2][1]*dd)
    a=e[3][0]+e[3][1]*dd; ecc=e[4][0]+e[4][1]*dd; M=norm(e[5][0]+e[5][1]*dd)
    E=math.radians(M)
    for _ in range(8): E=E-(E-ecc*math.sin(E)-math.radians(M))/(1-ecc*math.cos(E))
    xv=a*(math.cos(E)-ecc); yv=a*math.sqrt(1-ecc*ecc)*math.sin(E)
    v=math.atan2(yv,xv); r=math.hypot(xv,yv); lon=v+math.radians(w)
    Nr=math.radians(N); ir=math.radians(inc)
    return (r*(math.cos(Nr)*math.cos(lon)-math.sin(Nr)*math.sin(lon)*math.cos(ir)),
            r*(math.sin(Nr)*math.cos(lon)+math.cos(Nr)*math.sin(lon)*math.cos(ir)))
def glon(name,d):
    p=xyz(name,d); e=xyz("earth",d)
    return norm(math.degrees(math.atan2(p[1]-e[1],p[0]-e[0])))
def retro(d):
    a=glon("mercury",date.fromordinal(d.toordinal()-1)); b=glon("mercury",date.fromordinal(d.toordinal()+1))
    return ((b-a+540)%360)-180<0
def asp(a,b,target): return abs(adist(a,b)-target)<=6
def features(d):
    ph=lunar_phase_angle(d); L={p:glon(p,d) for p in ("mercury","mars","jupiter","saturn")}
    return {"lunar_phase_angle_deg":round(ph,6),"lunar_illumination":round(lunar_illumination(d),6),
      "NEW_MOON_WINDOW":adist(ph,0)<=24.4,"FULL_MOON_WINDOW":adist(ph,180)<=24.4,
      "FIRST_QUARTER_WINDOW":adist(ph,90)<=24.4,"LAST_QUARTER_WINDOW":adist(ph,270)<=24.4,
      "MERCURY_RETROGRADE":retro(d),
      "JUPITER_SATURN_CONJUNCTION":asp(L["jupiter"],L["saturn"],0),
      "JUPITER_SATURN_OPPOSITION":asp(L["jupiter"],L["saturn"],180),
      "JUPITER_SATURN_SQUARE":asp(L["jupiter"],L["saturn"],90),
      "JUPITER_SATURN_TRINE":asp(L["jupiter"],L["saturn"],120),
      "MARS_JUPITER_CONJUNCTION":asp(L["mars"],L["jupiter"],0),
      "MARS_JUPITER_OPPOSITION":asp(L["mars"],L["jupiter"],180),
      "MARS_JUPITER_SQUARE":asp(L["mars"],L["jupiter"],90)}
