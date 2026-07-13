#!/usr/bin/env python3
"""Probe: validate peer HDF fetch + response removal on a few stations for one UTC day."""
import urllib.request, io, sys, time
from obspy import read, read_inventory, UTCDateTime

BASE="https://data.raspberryshake.org/fdsnws"
DAY="2026-04-18"
t0=UTCDateTime(DAY+"T00:00:00"); t1=UTCDateTime(DAY+"T23:59:59.99")

def http(url):
    req=urllib.request.Request(url, headers={'User-Agent':'peer-baseline/1.0'})
    return urllib.request.urlopen(req, timeout=120).read()

def daily_hdf_rms(sta):
    ds=(f"{BASE}/dataselect/1/query?net=AM&sta={sta}&loc=00&cha=HDF"
        f"&start={DAY}T00:00:00&end={DAY}T23:59:59&format=miniseed&nodata=404")
    try:
        raw=http(ds)
    except Exception as e:
        return ("no-data", str(e)[:40])
    if not raw: return ("no-data","empty")
    try:
        st=read(io.BytesIO(raw))
    except Exception as e:
        return ("parse-fail", str(e)[:40])
    try:
        inv=read_inventory(io.BytesIO(http(
            f"{BASE}/station/1/query?net=AM&sta={sta}&loc=00&cha=HDF&level=response")))
    except Exception as e:
        return ("no-resp", str(e)[:40])
    st.merge(method=0)
    st=st.split()
    st.detrend("demean")
    # decimate to 20 Hz for tractability
    for tr in st:
        sr=tr.stats.sampling_rate
        if abs(sr-100.0)<1: tr.decimate(5, no_filter=False)
        elif abs(sr-50.0)<1: tr.decimate(2, no_filter=False)
    try:
        st.remove_response(inventory=inv, output="DEF",
                           pre_filt=(0.05,0.1,8,9), water_level=60)
    except Exception as e:
        return ("resp-fail", str(e)[:50])
    # per-minute RMS
    import numpy as np
    mins={}
    for tr in st:
        data=tr.data.astype("float64"); sr=tr.stats.sampling_rate
        start=tr.stats.starttime
        n=int(sr*60)
        if n<=0: continue
        for i in range(0, len(data), n):
            seg=data[i:i+n]
            if len(seg)<n*0.5: continue
            seg=seg-seg.mean()
            m=int((start+i/sr).timestamp//60)
            mins[m]=float(np.sqrt(np.mean(seg**2)))
    if not mins: return ("no-min","0")
    vals=list(mins.values())
    return ("ok", (len(vals), round(sum(vals)/len(vals),4), round(max(vals),4)))

tests=sys.argv[1:] or ["R0044","R0066","R0038"]
for sta in tests:
    ts=time.time()
    r=daily_hdf_rms(sta)
    print(sta, r, f"{time.time()-ts:.1f}s")
