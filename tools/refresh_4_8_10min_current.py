#!/usr/bin/env python3
"""Refresh the Apr-12-scoped R6E8A HDF 4-8 Hz record from the audited Aug-12 base.

Historical base comes from the corrected per-minute spectral archive and is fixed
through 2026-08-12T19:13:00Z. This script fetches/classifies only the public FDSN
tail after that point, using the exact same complete-minute Welch method.
"""
from __future__ import annotations
import io, json, math, time, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from obspy import UTCDateTime, read
from scipy.signal import welch

ROOT=Path(__file__).resolve().parents[1]
BASE_FILE=ROOT/'data'/'r6e8a_4_8_base_10min_2026-08-12.json'
OUT=ROOT/'data'/'r6e8a_4_8_10min_full.json'
FDSN='https://data.raspberryshake.org/fdsnws/dataselect/1/query'
TZ=ZoneInfo('America/Detroit')
BANDS=(("1-4",1.,4.),("4-8",4.,8.),("8-16",8.,16.),("16-20",16.,20.))
PREVIEW_END=datetime(2026,8,15,21,2,tzinfo=timezone.utc)
PREVIEW_EXPECTED={
 'analyzed_minutes':152884,'dom48_minutes':56472,
 'count15':608,'mins15':31965,'count30':324,'mins30':26113,
 'count60':159,'mins60':19212,'ordinance_events':74
}

def iz(dt): return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def http(url,tries=5,timeout=180):
    last=None
    for k in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'r6e8a-10min-tail/1.0'})
            with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()
        except Exception as e:
            last=e
            if getattr(e,'code',None) in (204,404):return None
            time.sleep(3*(k+1))
    raise last

def complete(st,m):
    t0=UTCDateTime(m)
    for tr in st:
        sr=float(tr.stats.sampling_rate)
        if not 95<=sr<=105: continue
        n=int(round(sr*60)); dt=1/sr
        if tr.stats.starttime>t0+dt/2 or tr.stats.endtime<t0+60-dt*1.5: continue
        i=int(round((t0-tr.stats.starttime)*sr))
        if i<0 or i+n>len(tr.data): continue
        x=tr.data[i:i+n]
        if len(x)!=n or (np.ma.isMaskedArray(x) and np.any(np.ma.getmaskarray(x))):continue
        x=np.asarray(x,dtype=np.float64)
        if np.all(np.isfinite(x)):return x,sr
    return None

def classify(x,sr):
    nper=min(int(round(sr*8)),len(x)); nover=min(nper//2,nper-1)
    f,p=welch(x,fs=sr,window='hann',nperseg=nper,noverlap=nover,detrend='constant',scaling='density')
    vals=[]
    for j,(name,lo,hi) in enumerate(BANDS):
        mask=(f>=lo)&((f<=hi) if j==len(BANDS)-1 else (f<hi))
        vals.append(float(np.mean(p[mask])) if np.any(mask) else -math.inf)
    return BANDS[int(np.argmax(vals))][0]

def fetch(start,end):
    out={}; latest=None; urls=[]; cur=start
    while cur<end:
        e=min(cur+timedelta(hours=6),end)
        url=f'{FDSN}?net=AM&sta=R6E8A&loc=00&cha=HDF&start={iz(cur)}&end={iz(e)}&format=miniseed&nodata=404'
        urls.append(url); raw=http(url)
        if raw:
            st=read(io.BytesIO(raw)); st.merge(method=0,fill_value=None)
            for tr in st:
                z=tr.stats.endtime.datetime.replace(tzinfo=timezone.utc)
                latest=z if latest is None or z>latest else latest
            m=cur.replace(second=0,microsecond=0)
            if m<cur:m+=timedelta(minutes=1)
            while m<e:
                g=complete(st,m)
                if g: out[int(m.timestamp())]=classify(*g)
                m+=timedelta(minutes=1)
        cur=e; time.sleep(.25)
    return out,latest,urls

def runs48(data):
    runs=[]; cur=[]; prev=None
    for t in sorted(data):
        b=data[t]
        if b=='4-8':
            if cur and prev is not None and t==prev+60:cur.append(t)
            else:
                if cur:runs.append(cur)
                cur=[t]
        else:
            if cur:runs.append(cur);cur=[]
        prev=t
    if cur:runs.append(cur)
    return runs

def night(t):
    d=datetime.fromtimestamp(t,timezone.utc).astimezone(TZ)
    return d.hour<7 or d.hour >= (23 if d.weekday() in (4,5) else 22)
def ordcount(runs):return sum(1 for r in runs if len(r)>=30 and sum(night(t) for t in r)>=30)
def poststats(data):
    c=Counter(data.values()); rr=runs48(data); x={'analyzed_minutes':len(data),'dom48_minutes':c['4-8'],'band_counts':dict(c),'runs_total':len(rr)}
    for q in (10,15,30,60):
        a=[r for r in rr if len(r)>=q];x[f'count{q}']=len(a);x[f'mins{q}']=sum(len(r) for r in a)
    x['ordinance_events']=ordcount(rr);return x,rr

def combine(base,post):
    ps,rr=poststats(post); x={}
    x['analyzed_minutes']=base['analyzed_minutes']+ps['analyzed_minutes'];x['dom48_minutes']=base['dom48_minutes']+ps['dom48_minutes']
    x['band_counts']={k:base['band_counts'].get(k,0)+ps['band_counts'].get(k,0) for k,_,_ in BANDS}
    for q in (10,15,30,60):
        x[f'count{q}']=base[f'count{q}']+ps[f'count{q}'];x[f'mins{q}']=base[f'mins{q}']+ps[f'mins{q}'];x[f'hours{q}']=round(x[f'mins{q}']/60,2)
    x['dom48_hours']=round(x['dom48_minutes']/60,2);x['dom48_percent_of_analyzed']=round(100*x['dom48_minutes']/x['analyzed_minutes'],2)
    x['shorter10_minutes']=x['dom48_minutes']-x['mins10'];x['shorter10_hours']=round(x['shorter10_minutes']/60,2)
    x['ordinance_events']=base['ordinance_events']+ps['ordinance_events']
    postlong=max((len(r) for r in rr),default=0); x['longest_minutes']=max(base['longest_minutes'],postlong)
    x['longest_runs']=[{'duration_minutes':x['longest_minutes'],'duration_hours':round(x['longest_minutes']/60,2)}]
    x['post']={**ps,'ordinance_events':ps['ordinance_events']}
    return x,rr

def sub(data,end):
    e=int(end.timestamp());return {t:b for t,b in data.items() if t<e}

def main():
    bdoc=json.loads(BASE_FILE.read_text()); base=bdoc['base']; start=datetime.fromisoformat(bdoc['end_exclusive_utc'])
    end=(datetime.now(timezone.utc)-timedelta(minutes=30)).replace(second=0,microsecond=0)
    post,latest,urls=fetch(start,end)
    prev,_=combine(base,sub(post,PREVIEW_END)); cur,currr=combine(base,post)
    checks=[]
    checks.append({'name':'1_apr12_scope_and_preview_totals','pass':prev['analyzed_minutes']==PREVIEW_EXPECTED['analyzed_minutes'] and prev['dom48_minutes']==PREVIEW_EXPECTED['dom48_minutes'],'observed':{'analyzed_minutes':prev['analyzed_minutes'],'dom48_minutes':prev['dom48_minutes']},'expected':{k:PREVIEW_EXPECTED[k] for k in ('analyzed_minutes','dom48_minutes')}})
    checks.append({'name':'2_corrected_legacy_threshold_checkpoint','pass':all(prev[k]==PREVIEW_EXPECTED[k] for k in ('count15','mins15','count30','mins30','count60','mins60')),'observed':{k:prev[k] for k in ('count15','mins15','count30','mins30','count60','mins60')},'expected':{k:PREVIEW_EXPECTED[k] for k in ('count15','mins15','count30','mins30','count60','mins60')}})
    edge=[int((PREVIEW_END-timedelta(minutes=i)).timestamp()) for i in range(1,7)]
    checks.append({'name':'3_checkpoint_six_minute_edge','pass':all(post.get(t)=='4-8' for t in edge),'observed':[{'utc':datetime.fromtimestamp(t,timezone.utc).isoformat(),'band':post.get(t)} for t in sorted(edge)],'expected':'six consecutive 4-8-dominant minutes ending at Aug 15 5:02 PM ET edge'})
    checks.append({'name':'4_tail_minute_integrity','pass':len(post)==len(set(post)) and all(t%60==0 for t in post) and set(post.values()).issubset({b[0] for b in BANDS}),'observed':{'classified_minutes':len(post),'unique_minutes':len(set(post)),'bands':sorted(set(post.values()))},'expected':'unique complete clock minutes and defined bands only'})
    checks.append({'name':'5_10min_reconciliation_and_ordinance_anchor','pass':cur['mins10']+cur['shorter10_minutes']==cur['dom48_minutes'] and cur['count10']>=cur['count15']>=cur['count30']>=cur['count60'] and prev['ordinance_events']==PREVIEW_EXPECTED['ordinance_events'],'observed':{'mins10':cur['mins10'],'shorter10_minutes':cur['shorter10_minutes'],'dom48_minutes':cur['dom48_minutes'],'counts':[cur['count10'],cur['count15'],cur['count30'],cur['count60']],'preview_ordinance_events':prev['ordinance_events']},'expected':'10+shorter=all 4-8; nested thresholds; preview ordinance=74'})
    latestcomplete=max(post) if post else None
    payload={'schema_version':3,'station':'AM.R6E8A.00','channel':'HDF','analysis_start_et':bdoc['scope_start_et'],'analysis_start_utc':bdoc['scope_start_utc'],'base_end_exclusive_utc':bdoc['end_exclusive_utc'],'generated_utc':datetime.now(timezone.utc).isoformat(),'lag_allowance_minutes':30,'requested_through_utc':end.isoformat(),'latest_returned_sample_utc':latest.isoformat() if latest else None,'latest_complete_analyzed_minute_utc':datetime.fromtimestamp(latestcomplete,timezone.utc).isoformat() if latestcomplete else None,'source':'Raspberry Shake public FDSN DataSelect + audited corrected per-minute archive through Aug 12','base_provenance':bdoc['source_archive'],'method':bdoc['method'],'preview_checkpoint':{'end_exclusive_utc':PREVIEW_END.isoformat(),'recomputed':prev,'expected':PREVIEW_EXPECTED},'current':cur,'checks':checks,'all_five_checks_pass':all(c['pass'] for c in checks),'fdsn_urls':urls,'publication_note':'No extrapolated hours. Apr 12 scope excludes 89 pre-scope non-4-8 minutes. The >=10-minute threshold is a reporting/event-definition choice, not a medical or legal exposure limit.'}
    OUT.write_text(json.dumps(payload,indent=2));print(json.dumps({'all_five_checks_pass':payload['all_five_checks_pass'],'current':cur,'checks':checks,'latest_returned_sample_utc':payload['latest_returned_sample_utc']},indent=2))
    if not payload['all_five_checks_pass']:raise SystemExit('Five-pass validation failed; dashboard must not be updated.')
if __name__=='__main__':main()
