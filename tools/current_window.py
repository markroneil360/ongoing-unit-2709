#!/usr/bin/env python3
import io,json,datetime,urllib.request,time,os
from zoneinfo import ZoneInfo
import numpy as np
from obspy import read,read_inventory,UTCDateTime
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE='https://data.raspberryshake.org/fdsnws'
TZ=ZoneInfo('America/Detroit')
PREFILT=(0.05,0.1,8,9)
# External comparison means. R6E8A is excluded and is never used to benchmark itself.
CFG={
 'HDF':{'output':'DEF','scale':1.0,'external_reference_mean':0.08119,'unit':'Pa','baseline_source':'independent external HDF environmental reference','r6e8a_excluded':True},
 'EHZ':{'output':'VEL','scale':1e6,'external_reference_mean':1.37637,'unit':'um/s','baseline_source':'independent external EHZ environmental reference','r6e8a_excluded':True}
}

def get(url,tries=4):
    last=None
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'r6e8a-current/1.1'}),timeout=180).read()
        except Exception as e:
            last=e; time.sleep(4*(i+1))
    raise last

def metrics(chan,t0,t1,inv):
    url=(f'{BASE}/dataselect/1/query?net=AM&sta=R6E8A&loc=00&cha={chan}'
         f'&start={t0.isoformat()}&end={t1.isoformat()}&format=miniseed&nodata=404')
    raw=get(url); st=read(io.BytesIO(raw)); st.trim(t0,t1,pad=False,nearest_sample=False)
    st.merge(method=0); st=st.split(); st.detrend('demean')
    for tr in st:
        factor=int(round(tr.stats.sampling_rate/20.0))
        if factor>=2: tr.decimate(factor,no_filter=False)
    cfg=CFG[chan]
    st.remove_response(inventory=inv,output=cfg['output'],pre_filt=PREFILT,water_level=60)
    vals=[]; latest=None
    for tr in st:
        x=tr.data.astype('float64')*cfg['scale']; sr=tr.stats.sampling_rate; n=max(1,int(round(sr*60)))
        for i in range(0,len(x),n):
            seg=x[i:i+n]
            if len(seg)<n*.5: continue
            seg=seg-seg.mean(); vals.append(float(np.sqrt(np.mean(seg**2))))
        latest=max(latest,tr.stats.endtime) if latest else tr.stats.endtime
    observed=float(np.mean(vals)) if vals else None
    reference=cfg['external_reference_mean']
    return {
      'channel':chan,'unit':cfg['unit'],
      'r6e8a_window_mean':observed,
      'external_reference_mean':reference,
      'baseline_source':cfg['baseline_source'],
      'r6e8a_excluded_from_baseline':cfg['r6e8a_excluded'],
      'percent_above_external_reference':round((observed/reference-1)*100,1) if observed is not None else None,
      'coverage_percent':round(100*len(vals)/1440,1),'minutes':len(vals),
      'data_through_et':latest.datetime.replace(tzinfo=datetime.timezone.utc).astimezone(TZ).isoformat() if latest else None,
      'provenance_url':url}

def main():
    now=datetime.datetime.now(TZ)
    cutoff=now.replace(hour=11,minute=0,second=0,microsecond=0)
    if now<cutoff: cutoff-=datetime.timedelta(days=1)
    start=cutoff-datetime.timedelta(days=1)
    t0=UTCDateTime(start.astimezone(datetime.timezone.utc)); t1=UTCDateTime(cutoff.astimezone(datetime.timezone.utc))
    inv=read_inventory(f'{BASE}/station/1/query?net=AM&sta=R6E8A&loc=00&cha=HDF,EHZ&level=response')
    data={'station':'AM.R6E8A.00','window_start_et':start.isoformat(),'window_end_et':cutoff.isoformat(),
          'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'cutoff_rule':'11:00 AM America/Detroit to 11:00 AM next day',
          'benchmark_rule':'R6E8A observed means are compared only with independent external channel-specific reference means; R6E8A is excluded from the benchmark.',
          'channels':{}}
    for c in ('HDF','EHZ'):
        data['channels'][c]=metrics(c,t0,t1,inv); time.sleep(2)
    os.makedirs(f'{ROOT}/data',exist_ok=True)
    with open(f'{ROOT}/data/current-window.json','w') as f: json.dump(data,f,indent=2)
if __name__=='__main__': main()
