from __future__ import annotations
import calendar
from datetime import date, timedelta

def _easter_sunday(year:int)->date:
    a=year%19;b=year//100;c=year%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32+2*e+2*i-h-k)%7;m=(a+11*h+22*l)//451
    month=(h+l-7*m+114)//31;day=((h+l-7*m+114)%31)+1
    return date(year,month,day)

def _observed_fixed(month:int,day:int,year:int)->date:
    d=date(year,month,day)
    if d.weekday()==5:return d-timedelta(days=1)
    if d.weekday()==6:return d+timedelta(days=1)
    return d

def _nth_weekday(year,month,weekday,n):
    d=date(year,month,1);shift=(weekday-d.weekday())%7
    return d+timedelta(days=shift+7*(n-1))

def _last_weekday(year,month,weekday):
    d=date(year,month,calendar.monthrange(year,month)[1])
    return d-timedelta(days=(d.weekday()-weekday)%7)

def nyse_holidays(year:int)->set[date]:
    easter=_easter_sunday(year)
    holidays={
        _observed_fixed(1,1,year),
        _nth_weekday(year,1,0,3),
        _nth_weekday(year,2,0,3),
        easter-timedelta(days=2),
        _last_weekday(year,5,0),
        _observed_fixed(6,19,year),
        _observed_fixed(7,4,year),
        _nth_weekday(year,9,0,1),
        _nth_weekday(year,11,3,4),
        _observed_fixed(12,25,year),
    }
    nxt=_observed_fixed(1,1,year+1)
    if nxt.year==year: holidays.add(nxt)
    return holidays

def is_regular_nyse_session(d:date)->bool:
    return d.weekday()<5 and d not in nyse_holidays(d.year)

def last_regular_nyse_session_of_month(year:int,month:int)->date:
    d=date(year,month,calendar.monthrange(year,month)[1])
    while not is_regular_nyse_session(d): d-=timedelta(days=1)
    return d

def completed_monthly_anchor(source:date)->date:
    cur=last_regular_nyse_session_of_month(source.year,source.month)
    if source>=cur:return cur
    y,m=(source.year-1,12) if source.month==1 else (source.year,source.month-1)
    return last_regular_nyse_session_of_month(y,m)

def completed_weekly_anchor(source:date)->date:
    monday=source-timedelta(days=source.weekday())
    friday=monday+timedelta(days=4)
    end=friday
    while not is_regular_nyse_session(end): end-=timedelta(days=1)
    if source>=end:return end
    end=monday-timedelta(days=3)
    while not is_regular_nyse_session(end): end-=timedelta(days=1)
    return end

def is_actual_month_end_session(source:date)->bool:
    return source==last_regular_nyse_session_of_month(source.year,source.month)
