#!/usr/bin/env python3
from __future__ import annotations
import io, json, math, hashlib, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
from obspy import UTCDateTime, Stream, read
from scipy.signal import welch

BASE='https://data.raspberryshake.org/fdsnws/dataselect/1/query'
TZ=ZoneInfo('America/Detroit')
UTC=timezone.utc
START_LOCAL=datetime(2026,9,3,17,0,0,tzinfo=TZ)
BANDS=(("1-4",1.,4.),("4-8",4.,8.),("8-16",8.,16.),("16-20",16.,20.))


def iso_z(dt): return dt.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

def fetch_chunks(ch,start,end,hours=6):
    st=Stream(); manifest=[]; latest=None; cur=start
    while cur<end:
        ce=min(cur+timedelta(hours=hours),end)
        url=(f'{BASE}?net=AM&sta=R6E8A&loc=00&cha={ch}'
             f'&start={iso_z(cur)}&end={iso_z(ce)}&format=miniseed&nodata=404')
        req=urllib.request.Request(url,headers={'User-Agent':'r6e8a-window-matrix/1.0'})
        with urllib.request.urlopen(req,timeout=180) as r: raw=r.read()
        sha=hashlib.sha256(raw).hexdigest()
        part=read(io.BytesIO(raw))
        if len(part):
            p_latest=max(tr.stats.endtime.datetime.replace(tzinfo=UTC) for tr in part)
            latest=p_latest if latest is None else max(latest,p_latest)
            st += part
        manifest.append({'channel':ch,'start_utc':iso_z(cur),'end_utc':iso_z(ce),'bytes':len(raw),'sha256':sha,'url':url})
        cur=ce
    st.merge(method=0,fill_value=None)
    return st,latest,manifest

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

def spectral_metrics(x,sr):
    nper=min(int(round(sr*8.0)),len(x)); nover=min(nper//2,nper-1)
    f,p=welch(x,fs=sr,window='hann',nperseg=nper,noverlap=nover,detrend='constant',scaling='density')
    means={}
    for i,(name,lo,hi) in enumerate(BANDS):
        mask=(f>=lo)&((f<=hi) if i==len(BANDS)-1 else (f<hi))
        means[name]=float(np.mean(p[mask])) if np.any(mask) else float('nan')
    band=max(means,key=lambda k:-math.inf if not math.isfinite(means[k]) else means[k])
    m=(f>=1.0)&(f<=20.0)
    pf=float(f[m][np.argmax(p[m])]) if np.any(m) else float('nan')
    return band,round(pf,3)

def classify(st,start,end):
    rows=[]; m=start.replace(second=0,microsecond=0)
    while m<end:
        got=extract_complete_minute(st,m)
        if got:
            x,sr=got; b,pf=spectral_metrics(x,sr); rows.append({'t':int(m.timestamp()),'band':b,'peak_hz':pf})
        m+=timedelta(minutes=1)
    return rows

def continuity(st,start,end):
    complete=0; m=start.replace(second=0,microsecond=0)
    while m<end:
        if extract_complete_minute(st,m) is not None: complete+=1
        m+=timedelta(minutes=1)
    expected=max(0,int((end-start).total_seconds()//60))
    return complete,expected,round(100*complete/expected,2) if expected else 0.0

def run_lengths(rows,target='4-8'):
    out=[]; cur=0; prev=None
    for r in rows:
        t=r['t']; b=r['band']
        if b==target and cur and prev is not None and t==prev+60: cur+=1
        elif b==target:
            if cur: out.append(cur)
            cur=1
        else:
            if cur: out.append(cur); cur=0
        prev=t
    if cur: out.append(cur)
    return out

def mode_peak(vals):
    c=Counter(vals)
    return sorted(c.items(),key=lambda kv:(-kv[1],kv[0]))[0][0] if c else None

def hour_key(epoch):
    d=datetime.fromtimestamp(epoch,UTC).astimezone(TZ)
    return d.replace(minute=0,second=0,microsecond=0)

def main():
    now=datetime.now(UTC)
    requested_end=(now-timedelta(minutes=30)).replace(second=0,microsecond=0)
    start=START_LOCAL.astimezone(UTC)
    if requested_end<=start: raise SystemExit('end <= start')
    hst,hlast,hmanifest=fetch_chunks('HDF',start,requested_end)
    est,elast,emanifest=fetch_chunks('EHZ',start,requested_end)
    common_latest=min(hlast,elast,requested_end)
    edge=(common_latest-timedelta(seconds=2)).replace(second=0,microsecond=0)
    rows=classify(hst,start,edge)
    h_complete,h_expected,h_cov=continuity(hst,start,edge)
    e_complete,e_expected,e_cov=continuity(est,start,edge)
    expected=int((edge-start).total_seconds()//60)
    overall_counts=Counter(r['band'] for r in rows)
    peaks=[r['peak_hz'] for r in rows if math.isfinite(r['peak_hz'])]
    byh=defaultdict(list)
    for r in rows: byh[hour_key(r['t'])].append(r)
    matrix=[]
    hk=START_LOCAL.replace(minute=0,second=0,microsecond=0)
    edge_local=edge.astimezone(TZ)
    while hk<edge_local:
        hr=byh.get(hk,[]); c=Counter(r['band'] for r in hr); p=[r['peak_hz'] for r in hr if math.isfinite(r['peak_hz'])]
        h_end=min(hk+timedelta(hours=1),edge_local)
        h_start=max(hk,START_LOCAL)
        exp=max(0,int((h_end-h_start).total_seconds()//60))
        dom=max(BANDS,key=lambda x:c[x[0]])[0] if hr else None
        matrix.append({
            'hour_et':hk.strftime('%Y-%m-%d %I:%M %p ET'),
            'expected_minutes':exp,'analyzed_minutes':len(hr),'coverage_pct':round(100*len(hr)/exp,2) if exp else 0.0,
            '1-4_min':c['1-4'],'4-8_min':c['4-8'],'8-16_min':c['8-16'],'16-20_min':c['16-20'],
            'dominant_band':dom,'4-8_pct':round(100*c['4-8']/len(hr),2) if hr else 0.0,
            'modal_peak_hz':mode_peak(p),'median_peak_hz':round(float(np.median(p)),3) if p else None
        })
        hk+=timedelta(hours=1)
    runs=run_lengths(rows)
    h_manifest_hash=hashlib.sha256(json.dumps(hmanifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    e_manifest_hash=hashlib.sha256(json.dumps(emanifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    overall={
        'expected_minutes':expected,'analyzed_minutes':len(rows),'coverage_pct':h_cov,
        'band_counts':{b:overall_counts[b] for b,_,_ in BANDS},
        'band_percent':{b:round(100*overall_counts[b]/len(rows),2) if rows else 0.0 for b,_,_ in BANDS},
        'modal_peak_hz':mode_peak(peaks),'median_peak_hz':round(float(np.median(peaks)),3) if peaks else None,
        '4_8_runs_total':len(runs),'events_ge_10m':sum(x>=10 for x in runs),'events_ge_30m':sum(x>=30 for x in runs),'events_ge_60m':sum(x>=60 for x in runs),'longest_4_8_run_min':max(runs) if runs else 0
    }
    core={
        'station':'AM.R6E8A.00','channel':'HDF','source':'Raspberry Shake public FDSN DataSelect',
        'window_start_et':START_LOCAL.isoformat(),'analyzed_edge_et':edge_local.isoformat(),
        'method':{'window':'clock-aligned complete 60-second HDF windows; gaps excluded','welch':'Hann; 8 s segments; 50% overlap','dominance':'highest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz','peak_hz':'highest Welch PSD bin from 1-20 Hz; nominal 0.125 Hz bin spacing at 100 Hz sample rate','missing':'excluded; never zero-filled or interpolated'},
        'raw_hdf_manifest_sha256':h_manifest_hash,'raw_ehz_manifest_sha256':e_manifest_hash,
        'overall':overall,'hourly_matrix':matrix,
        'EHZ_continuity':{'complete_minutes':e_complete,'expected_minutes':e_expected,'coverage_pct':e_cov}
    }
    canonical=json.dumps(core,sort_keys=True,separators=(',',':')).encode()
    findings_sha=hashlib.sha256(canonical).hexdigest()
    checks=[
        {'name':'1_identity_time_gate','pass':core['station']=='AM.R6E8A.00' and core['channel']=='HDF' and START_LOCAL.hour==17 and START_LOCAL.minute==0},
        {'name':'2_minute_and_hour_reconciliation','pass':len(rows)==len({r['t'] for r in rows}) and sum(overall_counts.values())==len(rows) and sum(x['analyzed_minutes'] for x in matrix)==len(rows)},
        {'name':'3_HDF_coverage_gate','pass':h_complete==len(rows) and h_expected==expected and h_cov>=99.0,'observed_pct':h_cov},
        {'name':'4_frequency_integrity_gate','pass':all(r['band'] in {x[0] for x in BANDS} and 1.0<=r['peak_hz']<=20.0 for r in rows)},
        {'name':'5_EHZ_separate_and_hash_gate','pass':e_expected==expected and e_cov>=99.0 and bool(findings_sha) and bool(h_manifest_hash) and bool(e_manifest_hash),'EHZ_coverage_pct':e_cov}
    ]
    result={**core,'generated_utc':datetime.now(UTC).isoformat(),'latest_samples':{'HDF_et':hlast.astimezone(TZ).isoformat(),'EHZ_et':elast.astimezone(TZ).isoformat()},'findings_sha256':findings_sha,'checks':checks,'all_five_checks_pass':all(c['pass'] for c in checks),'raw_HDF_chunks':hmanifest,'raw_EHZ_chunks':emanifest}
    open('/tmp/r6e8a_window_matrix.json','w').write(json.dumps(result,indent=2))
    print('R6E8A_WINDOW_MATRIX_BEGIN')
    print(json.dumps(result,indent=2))
    print('R6E8A_WINDOW_MATRIX_END')
    if not result['all_five_checks_pass']: raise SystemExit('Five-pass window validation failed')

if __name__=='__main__': main()
