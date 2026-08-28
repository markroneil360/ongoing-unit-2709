#!/usr/bin/env python3
from __future__ import annotations
import io, json, math, time, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from obspy import UTCDateTime, read
from scipy.signal import welch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'r6e8a_since_1am.json'
BASE = 'https://data.raspberryshake.org/fdsnws/dataselect/1/query'
TZ = ZoneInfo('America/Detroit')
UTC = timezone.utc
BANDS=(("1-4",1.,4.),("4-8",4.,8.),("8-16",8.,16.),("16-20",16.,20.))


def iso_z(dt): return dt.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

def fetch(ch,start,end):
    url=(f'{BASE}?net=AM&sta=R6E8A&loc=00&cha={ch}'
         f'&start={iso_z(start)}&end={iso_z(end)}&format=miniseed&nodata=404')
    req=urllib.request.Request(url,headers={'User-Agent':'r6e8a-since-1am/1.0'})
    with urllib.request.urlopen(req,timeout=180) as r: raw=r.read()
    st=read(io.BytesIO(raw)); st.merge(method=0,fill_value=None)
    latest=max(tr.stats.endtime.datetime.replace(tzinfo=UTC) for tr in st)
    return st,latest,url

def extract_complete_minute(st,dt):
    t0=UTCDateTime(dt)
    for tr in st:
        sr=float(tr.stats.sampling_rate)
        if not 95.0 <= sr <= 105.0: continue
        n=int(round(sr*60.0)); eps=1.0/sr
        if tr.stats.starttime > t0+eps/2: continue
        if tr.stats.endtime < t0+60.0-eps*1.5: continue
        i=int(round((t0-tr.stats.starttime)*sr))
        if i<0 or i+n>len(tr.data): continue
        x=tr.data[i:i+n]
        if len(x)!=n: continue
        if np.ma.isMaskedArray(x) and np.any(np.ma.getmaskarray(x)): continue
        x=np.asarray(x,dtype=np.float64)
        if np.all(np.isfinite(x)): return x,sr
    return None

def dominant_band(x,sr):
    nper=min(int(round(sr*8.0)),len(x)); nover=min(nper//2,nper-1)
    f,p=welch(x,fs=sr,window='hann',nperseg=nper,noverlap=nover,detrend='constant',scaling='density')
    means={}
    for i,(name,lo,hi) in enumerate(BANDS):
        mask=(f>=lo)&((f<=hi) if i==len(BANDS)-1 else (f<hi))
        means[name]=float(np.mean(p[mask])) if np.any(mask) else float('nan')
    return max(means,key=lambda k:-math.inf if not math.isfinite(means[k]) else means[k])

def classify(st,start,end):
    rows=[]; m=start.replace(second=0,microsecond=0)
    while m<end:
        got=extract_complete_minute(st,m)
        if got:
            x,sr=got; rows.append((int(m.timestamp()),dominant_band(x,sr)))
        m+=timedelta(minutes=1)
    return rows

def runs48(rows):
    out=[]; cur=[]; prev=None
    for t,b in rows:
        if b=='4-8' and cur and prev is not None and t==prev+60: cur.append(t)
        elif b=='4-8':
            if cur: out.append(cur)
            cur=[t]
        else:
            if cur: out.append(cur); cur=[]
        prev=t
    if cur: out.append(cur)
    return out

def channel_continuity(st,start,edge):
    complete=0; m=start.replace(second=0,microsecond=0)
    while m<edge:
        if extract_complete_minute(st,m) is not None: complete+=1
        m+=timedelta(minutes=1)
    expected=max(0,int((edge-start).total_seconds()//60))
    return complete, expected, round(100*complete/expected,2) if expected else 0.0

def main():
    now=datetime.now(UTC)
    local=now.astimezone(TZ)
    start_local=local.replace(hour=1,minute=0,second=0,microsecond=0)
    start=start_local.astimezone(UTC)
    requested_end=(now-timedelta(minutes=30)).replace(second=0,microsecond=0)
    if requested_end<=start: raise SystemExit('Requested edge is not after 1:00 AM ET')

    hst,hlast,hurl=fetch('HDF',start,requested_end)
    est,elast,eurl=fetch('EHZ',start,requested_end)
    common_latest=min(hlast,elast,requested_end)
    edge=(common_latest-timedelta(seconds=2)).replace(second=0,microsecond=0)
    rows=classify(hst,start,edge)
    counts=Counter(b for _,b in rows); runs=runs48(rows)
    dom48=counts['4-8']; total=len(rows)
    durations=[len(r) for r in runs]
    h_complete,h_expected,h_cov=channel_continuity(hst,start,edge)
    e_complete,e_expected,e_cov=channel_continuity(est,start,edge)
    expected=int((edge-start).total_seconds()//60)

    result={
      'station':'AM.R6E8A.00','primary_channel':'HDF','seismic_channel':'EHZ',
      'source':'Raspberry Shake public FDSN DataSelect',
      'generated_utc':datetime.now(UTC).isoformat(),
      'window_start_et':start_local.isoformat(),
      'requested_end_utc':requested_end.isoformat(),
      'analyzed_edge_et':edge.astimezone(TZ).isoformat(),
      'latest_samples':{'HDF_et':hlast.astimezone(TZ).isoformat(),'EHZ_et':elast.astimezone(TZ).isoformat()},
      'HDF':{
        'complete_minutes_analyzed':total,'band_counts':dict(counts),
        'dominant_4_8_minutes':dom48,'dominant_4_8_hours':round(dom48/60,2),
        'dominant_4_8_percent':round(100*dom48/total,2) if total else 0.0,
        'runs_4_8_total':len(runs),'longest_4_8_run_minutes':max(durations) if durations else 0,
        'events_ge_15m':sum(d>=15 for d in durations),'events_ge_30m':sum(d>=30 for d in durations),'events_ge_60m':sum(d>=60 for d in durations),
        'coverage_complete_minutes':h_complete,'coverage_expected_minutes':h_expected,'coverage_pct':h_cov,
        'url':hurl},
      'EHZ':{'coverage_complete_minutes':e_complete,'coverage_expected_minutes':e_expected,'coverage_pct':e_cov,'url':eurl},
      'method':{'window':'clock-aligned complete 60-second HDF windows; gaps excluded','welch':'Hann; 8 s segments; 50% overlap','dominance':'highest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz','missing':'excluded; never zero-filled or interpolated'},
    }
    checks=[
      {'name':'1_identity_time_gate','pass':result['station']=='AM.R6E8A.00' and result['primary_channel']=='HDF' and start_local.hour==1 and start_local.minute==0},
      {'name':'2_HDF_minute_integrity','pass':total==len(set(t for t,_ in rows)) and all(t%60==0 for t,_ in rows) and sum(counts.values())==total},
      {'name':'3_HDF_coverage_gate','pass':h_expected==expected and h_complete==total and h_cov>=99.0,'observed_pct':h_cov},
      {'name':'4_4_8_arithmetic_gate','pass':dom48==sum(durations) and 0<=dom48<=total and abs((dom48/60)-result['HDF']['dominant_4_8_hours'])<0.01},
      {'name':'5_EHZ_separate_continuity_gate','pass':e_expected==expected and e_cov>=99.0 and abs((hlast-elast).total_seconds())<5.0,'observed_pct':e_cov},
    ]
    result['checks']=checks; result['all_five_checks_pass']=all(c['pass'] for c in checks)
    OUT.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'all_five_checks_pass':result['all_five_checks_pass'],'window_start_et':result['window_start_et'],'analyzed_edge_et':result['analyzed_edge_et'],'latest_samples':result['latest_samples'],'HDF':result['HDF'],'EHZ':result['EHZ'],'checks':checks},indent=2))
    if not result['all_five_checks_pass']: raise SystemExit('Five-pass since-1am validation failed')

if __name__=='__main__': main()
