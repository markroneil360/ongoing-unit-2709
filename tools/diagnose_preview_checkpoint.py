#!/usr/bin/env python3
"""Read-only FDSN checkpoint diagnosis; never changes publishable cumulative data."""
from __future__ import annotations
import hashlib, io, json, platform, sys, traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import obspy, scipy
from obspy import read

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import refresh_4_8_10min_current as calc

REPORT = ROOT / 'data/r6e8a-checkpoint-diagnostic.json'
MINUTES = ROOT / 'data/r6e8a-checkpoint-minutes.json'
RAW = ROOT / 'diagnostic-raw'

def iso(t): return t.isoformat()
def main():
    bdoc = json.loads((ROOT/'data/r6e8a_4_8_base_10min_2026-08-12.json').read_text())
    old = json.loads((ROOT/'data/r6e8a_4_8_10min_full.json').read_text())
    start = datetime.fromisoformat(bdoc['end_exclusive_utc'])
    end = calc.PREVIEW_END
    minutes = {}; chunks = []; missing = []
    RAW.mkdir(exist_ok=True)
    report = {'purpose':'diagnosis only; not publishable cumulative data', 'publication_allowed':False,
      'station':'AM.R6E8A.00.HDF','start_utc':iso(start),'end_exclusive_utc':iso(end),
      'generated_et':datetime.now(ZoneInfo('America/Detroit')).isoformat(),
      'versions':{'python':platform.python_version(),'obspy':obspy.__version__,'numpy':np.__version__,'scipy':scipy.__version__},
      'expected_preview':old['preview_checkpoint']['recomputed'],'chunks':chunks,'missing_minute_utc':missing,
      'diagnostic_complete':False}
    def save():
        MINUTES.write_text(json.dumps({'station':'AM.R6E8A.00.HDF','publication_allowed':False,
           'start_utc':iso(start),'end_exclusive_utc':iso(end),'method':bdoc['method'],
           'minutes':[[t,minutes[t]] for t in sorted(minutes)]},separators=(',',':'))+'\n')
        report['classified_minutes']=len(minutes)
        report['minute_file_sha256']=hashlib.sha256(MINUTES.read_bytes()).hexdigest()
        REPORT.write_text(json.dumps(report,indent=2)+'\n')
    cur=start
    try:
        while cur<end:
            e=min(cur+timedelta(hours=6),end)
            url=f'{calc.FDSN}?net=AM&sta=R6E8A&loc=00&cha=HDF&start={calc.iz(cur)}&end={calc.iz(e)}&format=miniseed&nodata=404'
            raw=calc.http(url,tries=3,timeout=90)
            chunk={'start_utc':iso(cur),'end_utc':iso(e),'url':url,'bytes':len(raw or b''),'classified_minutes':0}
            chunks.append(chunk)
            if raw:
                chunk['sha256']=hashlib.sha256(raw).hexdigest()
                (RAW/f'{cur:%Y%m%dT%H%M%S}.mseed').write_bytes(raw)
                st=read(io.BytesIO(raw))
                chunk['identities']=sorted({tr.id for tr in st})
                assert chunk['identities']==['AM.R6E8A.00.HDF'],chunk['identities']
                chunk['traces']=[{'id':tr.id,'start_utc':str(tr.stats.starttime),'end_utc':str(tr.stats.endtime),'sample_rate':float(tr.stats.sampling_rate),'npts':int(tr.stats.npts)} for tr in st]
                chunk['raw_gaps']=[[str(x) if hasattr(x,'timestamp') else x for x in g] for g in st.get_gaps()]
                st.merge(method=0,fill_value=None)
            else: st=[]
            m=cur
            while m<e:
                got=calc.complete(st,m)
                if got:
                    minutes[int(m.timestamp())]=calc.classify(*got);chunk['classified_minutes']+=1
                else: missing.append(iso(m))
                m+=timedelta(minutes=1)
            save()
            print(json.dumps({'through':iso(e),'bytes':chunk['bytes'],'complete_minutes':chunk['classified_minutes'],'total_minutes':len(minutes),'missing':len(missing)}),flush=True)
            cur=e
        current,runs=calc.combine(bdoc['base'],minutes)
        report['observed_preview']=current
        fields=['analyzed_minutes','dom48_minutes','count10','mins10','count15','mins15','count30','mins30','count60','mins60','ordinance_events']
        expected=old['preview_checkpoint']['recomputed']
        report['comparison']={k:{'expected':expected[k],'observed':current[k],'difference':current[k]-expected[k]} for k in fields}
        report['all_preview_fields_match']=all(current[k]==expected[k] for k in fields) and current['band_counts']==expected['band_counts']
        report['diagnostic_complete']=True
        rr=calc.runs48(minutes)
        report['last_4_8_run']=calc.run_record(rr[-1]) if rr else None
    except Exception as exc:
        report['error']=str(exc);report['traceback']=traceback.format_exc()
    save()
    print(json.dumps({k:v for k,v in report.items() if k not in ('chunks','missing_minute_utc','expected_preview')},indent=2),flush=True)

if __name__=='__main__': main()
