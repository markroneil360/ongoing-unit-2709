#!/usr/bin/env python3
from __future__ import annotations
import io, json, math, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from obspy import UTCDateTime, read
from scipy.signal import welch

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'r6e8a_aug17_tail.json'
BASE='https://data.raspberryshake.org/fdsnws/dataselect/1/query'
TZ=ZoneInfo('America/Detroit')
UTC=timezone.utc
START=datetime(2026,8,18,2,40,tzinfo=UTC)  # 10:40 PM EDT
END=datetime(2026,8,18,3,30,tzinfo=UTC)    # 11:30 PM EDT exclusive
NEW_START=datetime(2026,8,18,2,41,tzinfo=UTC) # cache already includes 10:40 minute
BANDS=(("1-4",1.,4.),("4-8",4.,8.),("8-16",8.,16.),("16-20",16.,20.))

def fetch(ch):
    u=(f'{BASE}?net=AM&sta=R6E8A&loc=00&cha={ch}'
       f'&start={START.strftime("%Y-%m-%dT%H:%M:%S")}'
       f'&end={END.strftime("%Y-%m-%dT%H:%M:%S")}&format=miniseed&nodata=404')
    req=urllib.request.Request(u,headers={'User-Agent':'r6e8a-tail/1.0'})
    with urllib.request.urlopen(req,timeout=180) as r: raw=r.read()
    st=read(io.BytesIO(raw)); st.merge(method=0,fill_value=None)
    latest=max(tr.stats.endtime.datetime.replace(tzinfo=UTC) for tr in st)
    return st,latest,u

def minute(st,dt):
    t0=UTCDateTime(dt)
    for tr in st:
        sr=float(tr.stats.sampling_rate); n=int(round(sr*60)); eps=1/sr
        if not 95<=sr<=105: continue
        if tr.stats.starttime>t0+eps/2 or tr.stats.endtime<t0+60-eps*1.5: continue
        i=int(round((t0-tr.stats.starttime)*sr))
        if i<0 or i+n>len(tr.data): continue
        x=np.asarray(tr.data[i:i+n],dtype=float)
        if len(x)==n and np.all(np.isfinite(x)): return x,sr
    return None

def metrics(x,sr):
    nper=min(int(round(sr*8)),len(x)); nover=min(nper//2,nper-1)
    f,p=welch(x,fs=sr,window='hann',nperseg=nper,noverlap=nover,detrend='constant',scaling='density')
    means={}; powers={}
    for i,(name,lo,hi) in enumerate(BANDS):
        mask=(f>=lo)&((f<=hi) if i==len(BANDS)-1 else (f<hi)); ff=f[mask]; pp=p[mask]
        means[name]=float(np.mean(pp)) if len(pp) else float('nan')
        powers[name]=float(np.trapz(pp,ff)) if len(pp)>1 else 0.0
    dom=max(means,key=lambda k:-math.inf if not math.isfinite(means[k]) else means[k])
    mask=(f>=1)&(f<=20); ff=f[mask]; pp=p[mask]
    peak=float(ff[int(np.argmax(pp))]); total=float(np.trapz(pp,ff)); rms=math.sqrt(max(total,0.0))
    return {'dominant_band':dom,'peak_hz':peak,'rms_1_20_raw':rms,'band_power':powers}

def analyze(ch):
    st,latest,url=fetch(ch); rows=[]
    dt=START
    while dt<END:
        got=minute(st,dt)
        if got:
            x,sr=got; m=metrics(x,sr); m['utc']=dt.isoformat(); m['et']=dt.astimezone(TZ).isoformat(); rows.append(m)
        dt=dt.replace(second=0,microsecond=0)
        from datetime import timedelta
        dt+=timedelta(minutes=1)
    new=[r for r in rows if datetime.fromisoformat(r['utc'])>=NEW_START]
    return {'channel':ch,'latest_sample_utc':latest.isoformat(),'latest_sample_et':latest.astimezone(TZ).isoformat(),
            'requested_minutes':50,'complete_minutes':len(rows),'new_minutes_after_cached_1040':len(new),
            'all_band_counts':dict(Counter(r['dominant_band'] for r in rows)),
            'new_band_counts':dict(Counter(r['dominant_band'] for r in new)),
            'rows':rows,'url':url}

def main():
    h=analyze('HDF'); e=analyze('EHZ')
    checks=[
      {'name':'1_full_50_minute_tail_HDF','pass':h['complete_minutes']==50,'observed':h['complete_minutes'],'expected':50},
      {'name':'2_full_50_minute_tail_EHZ','pass':e['complete_minutes']==50,'observed':e['complete_minutes'],'expected':50},
      {'name':'3_new_minutes_reconcile','pass':h['new_minutes_after_cached_1040']==49 and e['new_minutes_after_cached_1040']==49,'observed':[h['new_minutes_after_cached_1040'],e['new_minutes_after_cached_1040']],'expected':[49,49]},
      {'name':'4_band_counts_reconcile','pass':sum(h['new_band_counts'].values())==49 and sum(e['new_band_counts'].values())==49,'observed':[sum(h['new_band_counts'].values()),sum(e['new_band_counts'].values())],'expected':[49,49]},
      {'name':'5_returned_edge_covers_1130','pass':datetime.fromisoformat(h['latest_sample_utc'])>=END and datetime.fromisoformat(e['latest_sample_utc'])>=END,'observed':[h['latest_sample_et'],e['latest_sample_et']],'expected':'both returned edges >= 11:30 PM EDT'}]
    out={'station':'AM.R6E8A.00','requested_window_et':['2026-08-17T22:40:00-04:00','2026-08-17T23:30:00-04:00'],
         'source':'Raspberry Shake public FDSN DataSelect','HDF':h,'EHZ':e,'checks':checks,'all_five_checks_pass':all(c['pass'] for c in checks)}
    OUT.write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps({'all_five_checks_pass':out['all_five_checks_pass'],'HDF':{k:h[k] for k in ('latest_sample_et','complete_minutes','new_band_counts')},'EHZ':{k:e[k] for k in ('latest_sample_et','complete_minutes','new_band_counts')},'checks':checks},indent=2))
    if not out['all_five_checks_pass']: raise SystemExit('TAIL VALIDATION FAILED')
if __name__=='__main__': main()
