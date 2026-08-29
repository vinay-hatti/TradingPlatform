from datetime import date,timedelta
from trading_ai.historical_underlying_replay.m77_19_4_isolated_adapters import snapshot,daily_dates,monthly_dates
def rows():
 ds=[];d=date(2020,1,1)
 while len(ds)<330:
  if d.weekday()<5:ds.append(d)
  d+=timedelta(days=1)
 r=[]
 for i,x in enumerate(ds):r += [("SPY",x,100+i*.1),("AAA",x,50+i*.05)]
 return ds,r
def test_future_mutation_invariant():
 ds,r=rows();a=ds[300];b=snapshot(r,a);r2=r+[("SPY",ds[320],999999),("AAA",ds[320],.01)];assert snapshot(r2,a)==b
def test_deterministic():ds,r=rows();a=ds[300];assert snapshot(r,a)==snapshot(r,a)
def test_ranges():ds,_=rows();assert all(ds[252]<=x<=ds[300] for x in daily_dates(ds,ds[252],ds[300]));assert all(ds[252]<=x<=ds[300] for x in monthly_dates(ds,ds[252],ds[300]))
